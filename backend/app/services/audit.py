from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiAuditLog


async def log_ai_call(
    db: AsyncSession,
    *,
    workflow: str,
    provider: str,
    model: str,
    user_id: int | None = None,
    source_ids: dict | None = None,
    output_excerpt: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> AiAuditLog:
    entry = AiAuditLog(
        workflow=workflow,
        provider=provider,
        model=model,
        user_id=user_id,
        source_ids=source_ids,
        output_excerpt=output_excerpt[:500] if output_excerpt else None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    db.add(entry)
    await db.flush()
    return entry
