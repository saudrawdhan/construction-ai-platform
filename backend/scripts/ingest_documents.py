"""Embed the document corpus into document_embeddings for RAG.

Sources: generated_documents (emails, minutes, site reports, claim threads), documents
(notices, reports), and correspondence (claim notices). Each record's text is chunked,
embedded with the configured embedder, and stored with a back-reference to its source.
Idempotent: clears document_embeddings first. Uses the real embedder unless TESTING.
"""

import asyncio

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal, engine
from app.models import Correspondence, Document, DocumentEmbedding, GeneratedDocument
from app.services.chunking import chunk_text
from app.services.embeddings import get_embedder

BATCH = 256


async def _collect(db: AsyncSession) -> list[dict]:
    records: list[dict] = []

    for row in await db.scalars(select(GeneratedDocument)):
        body = f"{row.subject}\n{row.body}"
        for index, chunk in enumerate(chunk_text(body)):
            records.append(
                {
                    "source_type": "generated_document",
                    "source_id": row.id,
                    "project_id": row.project_id,
                    "chunk_index": index,
                    "content": chunk,
                }
            )

    for row in await db.scalars(select(Document)):
        body = f"{row.title}\n{row.content_summary}"
        for index, chunk in enumerate(chunk_text(body)):
            records.append(
                {
                    "source_type": "document",
                    "source_id": row.id,
                    "project_id": row.project_id,
                    "chunk_index": index,
                    "content": chunk,
                }
            )

    for row in await db.scalars(select(Correspondence)):
        body = f"{row.subject}\n{row.body}"
        for index, chunk in enumerate(chunk_text(body)):
            records.append(
                {
                    "source_type": "correspondence",
                    "source_id": row.id,
                    "project_id": row.project_id,
                    "chunk_index": index,
                    "content": chunk,
                }
            )

    return records


async def run() -> None:
    embedder = get_embedder()
    print(f"embedder: provider={embedder.provider} dim={embedder.dim}")

    async with AsyncSessionLocal() as db:
        records = await _collect(db)
        print(f"chunks to embed: {len(records)}")

        await db.execute(text("TRUNCATE document_embeddings RESTART IDENTITY"))

        embedded = 0
        for start in range(0, len(records), BATCH):
            batch = records[start : start + BATCH]
            vectors = await embedder.embed_documents([r["content"] for r in batch])
            for record, vector in zip(batch, vectors, strict=True):
                record["embedding"] = vector
                record["token_count"] = max(len(record["content"]) // 4, 1)
            await db.execute(DocumentEmbedding.__table__.insert(), batch)
            embedded += len(batch)
            print(f"  embedded {embedded}/{len(records)}")

        await db.commit()

        total = await db.scalar(select(text("count(*)")).select_from(DocumentEmbedding))
        by_source = await db.execute(
            text(
                "SELECT source_type, count(*) FROM document_embeddings GROUP BY source_type "
                "ORDER BY source_type"
            )
        )

    print(f"stored embeddings: {total}")
    for source_type, count in by_source:
        print(f"  {source_type}: {count}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
