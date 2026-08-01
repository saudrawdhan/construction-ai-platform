"""Shared helpers for AI workflows: memory injection (the reuse loop) and JSON parsing.

Every workflow retrieves relevant prior memories and injects them into its reasoning so past
decisions shape new recommendations; the returned ids are reported for source attribution.
"""

import json

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiMemory
from app.schemas.memory import MemoryCreate
from app.services.embeddings import get_embedder
from app.services.memory import create_memory, search_memories


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


async def record_workflow_memory(
    db: AsyncSession, *, data: MemoryCreate, supersede: bool = False
) -> AiMemory | None:
    """Persist a workflow finding to enterprise memory, keyed on the record it describes.

    A workflow can be re-run over the same record any number of times — on demand, or on a
    schedule — so writing unconditionally would multiply one fact into a row per run and bury
    genuine knowledge under near-identical copies. Two behaviours cover the cases that exist:

    Default (``supersede=False``): the first memory for a source wins and later runs write
    nothing. Right when the finding is a property of the record itself (a purchase request was
    incomplete), which does not become truer by being reviewed again.

    ``supersede=True``: the new memory replaces the live one for that source, which is marked
    with ``superseded_by_id`` and therefore drops out of retrieval (search and the copilot both
    filter on it) while remaining on file as history. Right when the finding is a moving
    position (this week's portfolio picture) where only the current one should be recalled.
    """
    # Selecting the live memories and then writing is a check-then-act sequence: two runs for the
    # same source that overlap would each find no predecessor and both insert, leaving duplicates
    # live (proven with five concurrent writes, which produced five live rows). A transaction-
    # scoped advisory lock keyed on the source serializes just this section — it needs no table,
    # no migration, and releases automatically on commit or rollback. Concurrency on any OTHER
    # source is unaffected, since the key differs.
    lock_key = f"workflow-memory:{data.source_type}:{data.source_id}:{data.project_id}"
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": lock_key}
    )

    query = select(AiMemory).where(
        AiMemory.source_type == data.source_type,
        AiMemory.superseded_by_id.is_(None),
    )
    query = query.where(
        AiMemory.source_id.is_(None)
        if data.source_id is None
        else AiMemory.source_id == data.source_id
    )
    if data.project_id is None:
        query = query.where(AiMemory.project_id.is_(None))
    else:
        query = query.where(AiMemory.project_id == data.project_id)

    live = list(await db.scalars(query))
    if live and not supersede:
        return None

    memory = await create_memory(db, get_embedder(), data, created_by="agent")
    for prior in live:
        # create_memory returns the EXISTING record when the summary is an exact repeat, so the
        # "new" memory can be one of the very rows being superseded. Pointing a row at itself
        # would set its own superseded_by_id and drop it out of every retrieval — the finding
        # would silently vanish. An unchanged finding simply keeps the record it already has.
        if prior.id != memory.id:
            prior.superseded_by_id = memory.id
    await db.flush()
    return memory


_ARABIC_PROSE = (
    "Write your entire response in Arabic (العربية). Keep record identifiers, codes and numbers "
    "exactly as given — translate the prose around them, never the values themselves."
)

# Deliberately separate from the prose instruction: these workflows parse the model's reply by key,
# so a translated key silently breaks extraction while still looking like a valid answer.
_ARABIC_JSON = (
    "Write every free-text VALUE in your JSON response in Arabic (العربية). The JSON field NAMES "
    "must stay exactly as specified in English, and identifiers, codes and numbers must be kept "
    "exactly as given."
)


def localize(system: str, language: str, *, json_mode: bool = False) -> str:
    """Append an output-language instruction to a system prompt when Arabic is requested.

    English is the prompts' own language, so it needs no instruction and the prompt is returned
    unchanged — that keeps the default path byte-identical to how every one of these workflows
    behaved before."""
    if (language or "en").lower() != "ar":
        return system
    return f"{system}\n\n{_ARABIC_JSON if json_mode else _ARABIC_PROSE}"


def language_note(language: str, *, json_mode: bool = False) -> str:
    """The same directive on its own, for a caller that must place it at the END of the user
    message instead of relying on the system prompt.

    Five of the six workflows follow the system-prompt instruction on their own. The purchase
    request review does not: its user message closes by naming the English JSON fields to return,
    and a small local model follows the most recent instruction it saw — observed answering in
    English on every attempt until the directive moved after that closing line. Returns an empty
    string for English so the caller appends nothing at all.
    """
    if (language or "en").lower() != "ar":
        return ""
    return _ARABIC_JSON if json_mode else _ARABIC_PROSE


def parse_json_object(raw: str) -> dict:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
