from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiConversation, AiMessage


async def get_or_create_conversation(
    db: AsyncSession,
    *,
    conversation_id: int | None,
    user_id: int | None,
    project_id: int | None,
    title: str,
) -> AiConversation:
    if conversation_id is not None:
        existing = await db.get(AiConversation, conversation_id)
        # A conversation belongs to whoever started it. An id for someone else's
        # conversation must never continue it — that would inherit their project scope
        # and history into this user's answer. Treat it exactly like no id was given.
        if existing is not None and existing.user_id == user_id:
            return existing
    conversation = AiConversation(user_id=user_id, project_id=project_id, title=title[:255])
    db.add(conversation)
    await db.flush()
    return conversation


async def add_message(
    db: AsyncSession, *, conversation_id: int, role: str, content: str
) -> None:
    db.add(AiMessage(conversation_id=conversation_id, role=role, content=content))
