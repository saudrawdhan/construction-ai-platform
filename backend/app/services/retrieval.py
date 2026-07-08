"""Hybrid retrieval over document_embeddings: dense vector search (pgvector cosine) and
sparse full-text search (Postgres tsvector), fused with Reciprocal Rank Fusion. Vector
handles semantics and cross-language matches; full-text nails exact tokens like a PO or
change-order number. RRF combines both without tuning score scales.
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocumentEmbedding
from app.schemas.search import SearchHit
from app.services.embeddings import EmbeddingClient

RRF_K = 60


async def _vector_candidates(
    db: AsyncSession, query_vector: list[float], project_id: int | None, pool: int
) -> list[int]:
    stmt = select(DocumentEmbedding.id)
    if project_id is not None:
        stmt = stmt.where(DocumentEmbedding.project_id == project_id)
    stmt = stmt.order_by(DocumentEmbedding.embedding.cosine_distance(query_vector)).limit(pool)
    return list(await db.scalars(stmt))


async def fulltext_candidates(
    db: AsyncSession, query: str, project_id: int | None, pool: int
) -> list[int]:
    # The literal 'simple' config matches the GIN index expression so the index is used.
    filter_clause = "AND project_id = :project_id " if project_id is not None else ""
    sql = text(
        "SELECT id FROM document_embeddings "
        "WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', :q) "
        + filter_clause
        + "ORDER BY ts_rank(to_tsvector('simple', content), plainto_tsquery('simple', :q)) DESC "
        "LIMIT :pool"
    )
    params: dict = {"q": query, "pool": pool}
    if project_id is not None:
        params["project_id"] = project_id
    result = await db.execute(sql, params)
    return [row[0] for row in result]


def reciprocal_rank_fusion(*ranked_lists: list[int]) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, identifier in enumerate(ranked, start=1):
            scores[identifier] = scores.get(identifier, 0.0) + 1.0 / (RRF_K + rank)
    return scores


async def hybrid_search(
    db: AsyncSession,
    embedder: EmbeddingClient,
    *,
    query: str,
    k: int = 8,
    project_id: int | None = None,
    pool: int = 30,
) -> list[SearchHit]:
    query_vector = await embedder.embed_query(query)
    vector_ids = await _vector_candidates(db, query_vector, project_id, pool)
    fulltext_ids = await fulltext_candidates(db, query, project_id, pool)

    scores = reciprocal_rank_fusion(vector_ids, fulltext_ids)
    if not scores:
        return []

    top_ids = sorted(scores, key=lambda i: scores[i], reverse=True)[:k]
    rows = await db.scalars(
        select(DocumentEmbedding).where(DocumentEmbedding.id.in_(top_ids))
    )
    by_id = {row.id: row for row in rows}

    hits: list[SearchHit] = []
    for identifier in top_ids:
        row = by_id.get(identifier)
        if row is None:
            continue
        hits.append(
            SearchHit(
                id=row.id,
                source_type=row.source_type,
                source_id=row.source_id,
                project_id=row.project_id,
                chunk_index=row.chunk_index,
                content=row.content,
                score=round(scores[identifier], 6),
            )
        )
    return hits
