from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.agents.core import ConstructionAgent
from app.api.deps import DbSession
from app.models import AgentRun, AgentSkill, User
from app.schemas.agent import (
    AgentRunRequest,
    AgentRunResult,
    AgentRunSummary,
    AgentStepOut,
    SkillRead,
    SkillRunRequest,
    SkillStatusUpdate,
)
from app.schemas.common import Page
from app.security.deps import require_roles
from app.security.rate_limit import rate_limiter
from app.security.roles import Role
from app.services import agent_skills as agent_skills_service
from app.services.embeddings import get_embedder
from app.services.llm import get_llm

router = APIRouter(prefix="/ai/agent", tags=["ai-agent"])

AgentRoles = Annotated[
    User,
    Depends(
        require_roles(
            Role.ADMIN, Role.EXECUTIVE, Role.PROJECT_MANAGER,
            Role.SITE_ENGINEER, Role.PROCUREMENT_OFFICER, Role.QA_QC,
        )
    ),
]

AdminOnly = Annotated[User, Depends(require_roles(Role.ADMIN))]

# Agent runs and the conversations they belong to are personal working history, not shared
# organizational output — the same reasoning that keeps /audit/ai-outputs admin/exec-only
# applies here. Every other operational role may only read their OWN runs; admin/executive
# retain oversight visibility, matching that existing precedent.
_OVERSIGHT_ROLES = {Role.ADMIN, Role.EXECUTIVE}


def _can_view_run(run: AgentRun, user: User) -> bool:
    return user.role in _OVERSIGHT_ROLES or run.user_id == user.id


async def _skill_names(db: DbSession, *ids: int | None) -> dict[int, str]:
    wanted = [i for i in ids if i is not None]
    if not wanted:
        return {}
    rows = await db.scalars(select(AgentSkill).where(AgentSkill.id.in_(wanted)))
    return {skill.id: skill.name for skill in rows}


def _result_from_run(run: AgentRun, names: dict[int, str]) -> AgentRunResult:
    return AgentRunResult(
        id=run.id, goal=run.goal, status=run.status, final_answer=run.final_answer or "",
        steps=[AgentStepOut(**step) for step in (run.steps or [])],
        sources=run.sources or [], step_count=run.step_count,
        skill_used=names.get(run.skill_used_id) if run.skill_used_id else None,
        skill_created=names.get(run.skill_created_id) if run.skill_created_id else None,
        provider=run.provider, model=run.model, conversation_id=run.conversation_id,
    )


@router.post(
    "/run",
    response_model=AgentRunResult,
    dependencies=[Depends(rate_limiter(times=20, seconds=60))],
)
async def run_agent(payload: AgentRunRequest, db: DbSession, user: AgentRoles) -> AgentRunResult:
    agent = ConstructionAgent(get_llm(), get_embedder())
    result = await agent.run(
        db, goal=payload.goal, project_id=payload.project_id,
        user_id=user.id, user_role=user.role, conversation_id=payload.conversation_id,
    )
    await db.commit()
    return result


@router.get("/runs", response_model=Page[AgentRunSummary])
async def list_runs(
    db: DbSession,
    user: AgentRoles,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[AgentRunSummary]:
    query = select(AgentRun)
    count_query = select(func.count()).select_from(AgentRun)
    if user.role not in _OVERSIGHT_ROLES:
        query = query.where(AgentRun.user_id == user.id)
        count_query = count_query.where(AgentRun.user_id == user.id)
    total = await db.scalar(count_query) or 0
    rows = list(
        await db.scalars(
            query.order_by(AgentRun.created_at.desc()).offset((page - 1) * size).limit(size)
        )
    )
    names = await _skill_names(
        db, *[r.skill_used_id for r in rows], *[r.skill_created_id for r in rows]
    )
    items = [
        AgentRunSummary(
            id=run.id, goal=run.goal, status=run.status, step_count=run.step_count,
            skill_used=names.get(run.skill_used_id) if run.skill_used_id else None,
            skill_created=names.get(run.skill_created_id) if run.skill_created_id else None,
            provider=run.provider, created_at=run.created_at,
        )
        for run in rows
    ]
    return Page.build(items, total, page, size)


@router.get("/runs/{run_id}", response_model=AgentRunResult)
async def get_run(run_id: int, db: DbSession, user: AgentRoles) -> AgentRunResult:
    run = await db.get(AgentRun, run_id)
    # Not found and not-yours are reported identically — confirming that some OTHER
    # user's run exists at this id is itself the kind of leak this check exists to close.
    if run is None or not _can_view_run(run, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    names = await _skill_names(db, run.skill_used_id, run.skill_created_id)
    return _result_from_run(run, names)


@router.get("/skills", response_model=list[SkillRead])
async def list_skills(db: DbSession, user: AgentRoles) -> list[SkillRead]:
    rows = await db.scalars(
        select(AgentSkill).order_by(AgentSkill.usage_count.desc(), AgentSkill.id.desc())
    )
    return [SkillRead.from_model(skill) for skill in rows]


@router.get("/skills/{skill_id}", response_model=SkillRead)
async def get_skill(skill_id: int, db: DbSession, user: AgentRoles) -> SkillRead:
    skill = await db.get(AgentSkill, skill_id)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return SkillRead.from_model(skill)


@router.patch("/skills/{skill_id}", response_model=SkillRead)
async def update_skill_status(
    skill_id: int, payload: SkillStatusUpdate, db: DbSession, _: AdminOnly
) -> SkillRead:
    skill = await agent_skills_service.set_skill_status(db, skill_id, payload.status)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Skill not found")
    await db.commit()
    await db.refresh(skill)
    return SkillRead.from_model(skill)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_skill(skill_id: int, db: DbSession, _: AdminOnly) -> None:
    deleted = await agent_skills_service.delete_skill(db, skill_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Skill not found")
    await db.commit()


@router.post(
    "/skills/{skill_id}/run",
    response_model=AgentRunResult,
    dependencies=[Depends(rate_limiter(times=20, seconds=60))],
)
async def run_skill(
    skill_id: int, payload: SkillRunRequest, db: DbSession, user: AgentRoles
) -> AgentRunResult:
    skill = await db.get(AgentSkill, skill_id)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Skill not found")
    agent = ConstructionAgent(get_llm(), get_embedder())
    result = await agent.run_skill(
        db, skill, goal=payload.goal, project_id=payload.project_id,
        user_id=user.id, user_role=user.role, conversation_id=payload.conversation_id,
    )
    if result is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="This skill's parameters cannot be resolved from the given goal.",
        )
    await db.commit()
    return result
