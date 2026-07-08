from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, GeneratedDocument


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
