"""Enterprise memory layer: store, retrieve, and reuse structured operational knowledge.

Every memory is embedded on write so it is findable by meaning; search is hybrid (vector +
full-text) and excludes superseded memories so only current knowledge is reused. This is the
substrate for the reuse loop — workflows inject relevant memories into their prompts.
"""

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiMemory
from app.schemas.memory import MemoryCreate
from app.services.embeddings import EmbeddingClient
from app.services.retrieval import reciprocal_rank_fusion


async def create_memory(
    db: AsyncSession,
    embedder: EmbeddingClient,
    data: MemoryCreate,
    *,
    created_by: str = "user",
) -> AiMemory:
    existing = await _find_exact_duplicate(db, data)
    if existing is not None:
        return existing
    embed_text = data.summary if not data.detail else f"{data.summary}\n{data.detail}"
    (vector,) = await embedder.embed_documents([embed_text])
    memory = AiMemory(
        project_id=data.project_id,
        category=data.category.value,
        summary=data.summary,
        detail=data.detail,
        source_type=data.source_type,
        source_id=data.source_id,
        source_excerpt=data.source_excerpt,
        confidence=data.confidence,
        created_by=created_by,
        embedding=vector,
    )
    db.add(memory)
    await db.flush()
    return memory


async def _find_exact_duplicate(db: AsyncSession, data: MemoryCreate) -> AiMemory | None:
    """An exact-duplicate summary in the same project/category scope adds retrieval noise
    without adding information — live audit testing found a duplicate memory surfaced twice,
    verbatim, in every search that matched it. Skip inserting a repeat and return the
    existing record instead. Conservative on purpose: only a case/whitespace-insensitive
    EXACT match is treated as a duplicate, so two genuinely different findings about the
    same project and category are never silently merged."""
    stmt = select(AiMemory).where(
        AiMemory.superseded_by_id.is_(None),
        AiMemory.category == data.category.value,
        func.lower(func.trim(AiMemory.summary)) == data.summary.strip().lower(),
    )
    stmt = stmt.where(
        AiMemory.project_id == data.project_id
        if data.project_id is not None
        else AiMemory.project_id.is_(None)
    )
    return await db.scalar(stmt.limit(1))


async def get_memory(db: AsyncSession, memory_id: int) -> AiMemory | None:
    return await db.get(AiMemory, memory_id)


async def delete_memory(db: AsyncSession, memory_id: int) -> bool:
    memory = await db.get(AiMemory, memory_id)
    if memory is None:
        return False
    await db.delete(memory)
    await db.flush()
    return True


async def list_memories(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    project_id: int | None = None,
    category: str | None = None,
) -> tuple[list[AiMemory], int]:
    query = select(AiMemory).where(AiMemory.superseded_by_id.is_(None))
    if project_id is not None:
        query = query.where(AiMemory.project_id == project_id)
    if category:
        query = query.where(AiMemory.category == category)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(AiMemory.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def _vector_candidates(db, query_vector, project_id, category, pool) -> list[int]:
    stmt = select(AiMemory.id).where(
        AiMemory.superseded_by_id.is_(None), AiMemory.embedding.is_not(None)
    )
    if project_id is not None:
        stmt = stmt.where(AiMemory.project_id == project_id)
    if category:
        stmt = stmt.where(AiMemory.category == category)
    stmt = stmt.order_by(AiMemory.embedding.cosine_distance(query_vector)).limit(pool)
    return list(await db.scalars(stmt))


async def memory_fulltext_candidates(db, query, project_id, category, pool) -> list[int]:
    clauses = "AND project_id = :project_id " if project_id is not None else ""
    clauses += "AND category = :category " if category else ""
    sql = text(
        "SELECT id FROM ai_memories "
        "WHERE superseded_by_id IS NULL "
        "AND to_tsvector('simple', summary) @@ plainto_tsquery('simple', :q) "
        + clauses
        + "ORDER BY ts_rank(to_tsvector('simple', summary), plainto_tsquery('simple', :q)) DESC "
        "LIMIT :pool"
    )
    params: dict = {"q": query, "pool": pool}
    if project_id is not None:
        params["project_id"] = project_id
    if category:
        params["category"] = category
    result = await db.execute(sql, params)
    return [row[0] for row in result]


async def search_memories(
    db: AsyncSession,
    embedder: EmbeddingClient,
    *,
    query: str,
    k: int = 5,
    project_id: int | None = None,
    category: str | None = None,
    pool: int = 20,
) -> list[tuple[AiMemory, float]]:
    query_vector = await embedder.embed_query(query)
    vector_ids = await _vector_candidates(db, query_vector, project_id, category, pool)
    fulltext_ids = await memory_fulltext_candidates(db, query, project_id, category, pool)

    scores = reciprocal_rank_fusion(vector_ids, fulltext_ids)
    if not scores:
        return []

    rows = await db.scalars(select(AiMemory).where(AiMemory.id.in_(list(scores))))
    by_id = {row.id: row for row in rows}

    # RRF alone ranks purely by retrieval-channel rank position, so a poorly-attested finding
    # can outrank a well-attested one that simply scored a fraction lower on textual/semantic
    # closeness — live-verified with a deliberately poisoned pair (a 0.2-confidence false claim
    # ranked above a 0.95-confidence correct one). A memory with no confidence set is treated as
    # moderately trustworthy rather than penalized, since most memories are never explicitly
    # rated. This only reorders the returned set; the relevance score shown to the caller stays
    # the raw RRF value so it keeps meaning "how well this matched," with confidence surfaced
    # separately (already shown per-memory) rather than folded into one blended number.
    def _rank_weight(memory_id: int) -> float:
        memory = by_id.get(memory_id)
        confidence = memory.confidence if memory and memory.confidence is not None else 0.7
        return scores[memory_id] * (0.5 + 0.5 * float(confidence))

    top_ids = sorted(scores, key=_rank_weight, reverse=True)[:k]
    return [(by_id[i], round(scores[i], 6)) for i in top_ids if i in by_id]
