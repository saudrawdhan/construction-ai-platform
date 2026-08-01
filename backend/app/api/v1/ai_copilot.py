from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.copilot import ConstructionCopilot
from app.api.deps import DbSession
from app.models import Project
from app.schemas.copilot import CopilotAnswer, CopilotChatRequest
from app.security.deps import CurrentUser
from app.security.rate_limit import rate_limiter
from app.services import audit as audit_service
from app.services import conversations as conversation_service
from app.services.llm import get_llm

router = APIRouter(prefix="/ai", tags=["ai-copilot"])


@router.post(
    "/copilot/chat",
    response_model=CopilotAnswer,
    dependencies=[Depends(rate_limiter(times=20, seconds=60))],
)
async def copilot_chat(
    payload: CopilotChatRequest, db: DbSession, user: CurrentUser
) -> CopilotAnswer:
    # Check the scope before spending a full model call on it. The conversation row this endpoint
    # writes carries a foreign key to projects, so an unknown project_id previously failed only at
    # commit — after the LLM had already run — and surfaced as an opaque constraint error.
    if payload.project_id is not None and await db.get(Project, payload.project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")

    copilot = ConstructionCopilot(get_llm())
    result = await copilot.answer(db, question=payload.question, project_id=payload.project_id)

    conversation = await conversation_service.get_or_create_conversation(
        db,
        conversation_id=payload.conversation_id,
        user_id=user.id,
        project_id=payload.project_id,
        title=payload.question,
    )
    await conversation_service.add_message(
        db, conversation_id=conversation.id, role="user", content=payload.question
    )
    await conversation_service.add_message(
        db, conversation_id=conversation.id, role="assistant", content=result.answer
    )
    await audit_service.log_ai_call(
        db,
        workflow="copilot",
        provider=result.provider,
        model=result.model,
        user_id=user.id,
        source_ids={"sources": [s.model_dump() for s in result.sources]},
        output_excerpt=result.answer,
    )
    await db.commit()

    return CopilotAnswer(
        conversation_id=conversation.id,
        question=payload.question,
        answer=result.answer,
        grounded=result.grounded,
        sources=result.sources,
        provider=result.provider,
        model=result.model,
    )
