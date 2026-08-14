from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from app.api.deps import DbSession
from app.api.v1.import_helpers import handle_tabular_import
from app.models import User
from app.schemas.common import Page
from app.schemas.imports import ImportReport
from app.schemas.project import (
    ProjectCreate,
    ProjectDecisionRead,
    ProjectIssueCreate,
    ProjectIssueRead,
    ProjectMilestoneCreate,
    ProjectMilestoneRead,
    ProjectRead,
    ProjectRiskCreate,
    ProjectRiskRead,
    ProjectUpdate,
)
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import projects as project_service

router = APIRouter(prefix="/projects", tags=["projects"])

ProjectManagers = Annotated[User, Depends(require_roles(Role.ADMIN, Role.PROJECT_MANAGER))]

PROJECT_TEMPLATE = (
    "project_code,project_name,project_type,client_name,city,status,"
    "start_date,planned_finish,budget\n"
    "PRJ-0100,Riyadh Office Tower,Tower,Gulf Energy Holdings,Riyadh,Active,"
    "2026-01-15,2027-06-30,250000000\n"
)


@router.get("/import/template")
async def project_import_template(_: ProjectManagers) -> Response:
    return Response(
        content=PROJECT_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=projects_template.csv"},
    )


@router.post("/import", response_model=ImportReport)
async def import_projects(
    db: DbSession,
    _: ProjectManagers,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Form()] = False,
) -> ImportReport:
    return await handle_tabular_import(
        db, file, dry_run, schema=ProjectCreate, create=project_service.create_project
    )


@router.get("", response_model=Page[ProjectRead])
async def list_projects(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: str | None = None,
    city: str | None = None,
    project_type: str | None = None,
) -> Page[ProjectRead]:
    items, total = await project_service.list_projects(
        db, page=page, size=size, status=status, city=city, project_type=project_type
    )
    return Page.build([ProjectRead.model_validate(p) for p in items], total, page, size)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, db: DbSession, _: ProjectManagers
) -> ProjectRead:
    project = await project_service.create_project(db, payload)
    await db.commit()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: int, db: DbSession, _: CurrentUser) -> ProjectRead:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int, payload: ProjectUpdate, db: DbSession, _: ProjectManagers
) -> ProjectRead:
    project = await project_service.update_project(db, project_id, payload)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    await db.commit()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, db: DbSession, _: ProjectManagers) -> None:
    if not await project_service.delete_project(db, project_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    await db.commit()


@router.get("/{project_id}/risks", response_model=list[ProjectRiskRead])
async def list_project_risks(
    project_id: int, db: DbSession, _: CurrentUser
) -> list[ProjectRiskRead]:
    if await project_service.get_project(db, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    risks = await project_service.list_risks(db, project_id)
    return [ProjectRiskRead.model_validate(r) for r in risks]


@router.post(
    "/{project_id}/risks",
    response_model=ProjectRiskRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_risk(
    project_id: int, payload: ProjectRiskCreate, db: DbSession, _: ProjectManagers
) -> ProjectRiskRead:
    if await project_service.get_project(db, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    risk = await project_service.create_risk(db, project_id, payload)
    await db.commit()
    await db.refresh(risk)
    return ProjectRiskRead.model_validate(risk)


async def _require_project(db: DbSession, project_id: int) -> None:
    if await project_service.get_project(db, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")


@router.get("/{project_id}/issues", response_model=list[ProjectIssueRead])
async def list_project_issues(
    project_id: int, db: DbSession, _: CurrentUser
) -> list[ProjectIssueRead]:
    await _require_project(db, project_id)
    issues = await project_service.list_issues(db, project_id)
    return [ProjectIssueRead.model_validate(i) for i in issues]


@router.post(
    "/{project_id}/issues",
    response_model=ProjectIssueRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_issue(
    project_id: int, payload: ProjectIssueCreate, db: DbSession, _: ProjectManagers
) -> ProjectIssueRead:
    await _require_project(db, project_id)
    issue = await project_service.create_issue(db, project_id, payload)
    await db.commit()
    await db.refresh(issue)
    return ProjectIssueRead.model_validate(issue)


@router.get("/{project_id}/milestones", response_model=list[ProjectMilestoneRead])
async def list_project_milestones(
    project_id: int, db: DbSession, _: CurrentUser
) -> list[ProjectMilestoneRead]:
    await _require_project(db, project_id)
    milestones = await project_service.list_milestones(db, project_id)
    return [ProjectMilestoneRead.model_validate(m) for m in milestones]


@router.post(
    "/{project_id}/milestones",
    response_model=ProjectMilestoneRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_milestone(
    project_id: int, payload: ProjectMilestoneCreate, db: DbSession, _: ProjectManagers
) -> ProjectMilestoneRead:
    await _require_project(db, project_id)
    milestone = await project_service.create_milestone(db, project_id, payload)
    await db.commit()
    await db.refresh(milestone)
    return ProjectMilestoneRead.model_validate(milestone)


@router.get("/{project_id}/decisions", response_model=list[ProjectDecisionRead])
async def list_project_decisions(
    project_id: int, db: DbSession, _: CurrentUser
) -> list[ProjectDecisionRead]:
    await _require_project(db, project_id)
    decisions = await project_service.list_decisions(db, project_id)
    return [ProjectDecisionRead.model_validate(d) for d in decisions]
