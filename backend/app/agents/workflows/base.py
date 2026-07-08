"""Shared helpers for AI workflows: memory injection (the reuse loop) and JSON parsing.

Every workflow retrieves relevant prior memories and injects them into its reasoning so past
decisions shape new recommendations; the returned ids are reported for source attribution.
"""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embeddings import get_embedder
from app.services.memory import search_memories


async def gather_memory_context(
    db: AsyncSession,
    *,
    query: str,
    project_id: int | None = None,
    category: str | None = None,
    k: int = 3,
) -> tuple[str, list[int]]:
    results = await search_memories(
        db, get_embedder(), query=query, k=k, project_id=project_id, category=category
    )
    if not results:
        return "No related operational memories on record.", []
    lines = [f"- [{memory.category}] {memory.summary}" for memory, _ in results]
    return "\n".join(lines), [memory.id for memory, _ in results]


def parse_json_object(raw: str) -> dict:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
