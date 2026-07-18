import asyncio
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentEmbedding, GeneratedDocument


async def list_documents(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    project_id: int | None = None,
    doc_type: str | None = None,
) -> tuple[list[Document], int]:
    query = select(Document)
    if project_id:
        query = query.where(Document.project_id == project_id)
    if doc_type:
        query = query.where(Document.doc_type == doc_type)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(query.order_by(Document.id).offset((page - 1) * size).limit(size))
    return list(rows), int(total or 0)


async def get_document(db: AsyncSession, document_id: int) -> Document | None:
    return await db.get(Document, document_id)


async def delete_document(db: AsyncSession, document_id: int) -> bool | None:
    """Remove a document, its indexed chunks, and its stored original file. Returns None if no
    such document exists. A document still referenced as claim evidence cannot be deleted — the
    foreign key raises, translated to a 409 by the app's global IntegrityError handler, the same
    FK-safe pattern every other entity delete uses.

    Deletion order matters: the chunk rows and the document row are staged and flushed FIRST so a
    foreign-key rejection aborts the whole request before anything irreversible happens; only once
    the database delete has succeeded is the file removed from disk, mirroring how ingest writes
    the file last so a failure never leaves the two stores inconsistent."""
    document = await db.get(Document, document_id)
    if document is None:
        return None
    storage_path = document.storage_path
    await db.execute(
        delete(DocumentEmbedding).where(
            DocumentEmbedding.source_type == "document",
            DocumentEmbedding.source_id == document_id,
        )
    )
    await db.delete(document)
    await db.flush()  # FK check here — a referenced document raises before the file is touched
    if storage_path:
        await asyncio.to_thread(Path(storage_path).unlink, missing_ok=True)
    return True


async def list_generated_documents(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    project_id: int | None = None,
    doc_type: str | None = None,
) -> tuple[list[GeneratedDocument], int]:
    query = select(GeneratedDocument)
    if project_id:
        query = query.where(GeneratedDocument.project_id == project_id)
    if doc_type:
        query = query.where(GeneratedDocument.type == doc_type)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(GeneratedDocument.id).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def get_generated_document(
    db: AsyncSession, document_id: int
) -> GeneratedDocument | None:
    return await db.get(GeneratedDocument, document_id)
