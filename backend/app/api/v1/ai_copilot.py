from fastapi import APIRouter, Depends

from app.agents.copilot import ConstructionCopilot
from app.api.deps import DbSession
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
