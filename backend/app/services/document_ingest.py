"""Ingest an uploaded file into the platform's knowledge base. Text is extracted from PDF,
Word, or plain-text files, a documents row is recorded, and the body is chunked and embedded
into document_embeddings — the same store the seeded corpus uses, so an uploaded file becomes
retrievable through the existing hybrid search and the copilot without any special-casing.
"""

import asyncio
from datetime import date
from io import BytesIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentEmbedding
from app.services.chunking import chunk_text
from app.services.embeddings import EmbeddingClient

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_TEXT_EXTENSIONS = (".txt", ".md", ".markdown", ".csv", ".log")


class UnsupportedDocument(ValueError):
    """Raised when a file's type is not one we can parse."""


class EmptyDocument(ValueError):
    """Raised when a supported file yields no extractable text (e.g. a scanned PDF)."""


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    from docx import Document as DocxDocument

    document = DocxDocument(BytesIO(data))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return _extract_pdf(data)
    if name.endswith(".docx"):
        return _extract_docx(data)
    if name.endswith(_TEXT_EXTENSIONS):
        return data.decode("utf-8", errors="ignore")
    raise UnsupportedDocument("Unsupported file type. Upload a PDF, DOCX, or text file.")


async def ingest_upload(
    db: AsyncSession,
    embedder: EmbeddingClient,
    *,
    project_id: int,
    doc_type: str,
    title: str,
    filename: str,
    data: bytes,
) -> tuple[Document, int, int]:
    """Extract, persist, chunk, and embed. Returns (document, chunk_count, character_count).

    Parsing runs in a worker thread because pypdf/python-docx are synchronous and a large
    file would otherwise block the event loop.
    """
    text = (await asyncio.to_thread(extract_text, filename, data)).strip()
    if not text:
        raise EmptyDocument("No readable text could be extracted from the file.")

    document = Document(
        project_id=project_id,
        doc_type=doc_type,
        title=title,
        doc_date=date.today(),
        content_summary=" ".join(text.split())[:500],
    )
    db.add(document)
    await db.flush()  # assign document.id before referencing it from the chunks

    chunks = chunk_text(text)
    vectors = await embedder.embed_documents(chunks)
    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        db.add(
            DocumentEmbedding(
                source_type="document",
                source_id=document.id,
                project_id=project_id,
                chunk_index=index,
                content=chunk,
                token_count=max(len(chunk) // 4, 1),
                embedding=vector,
            )
        )
    return document, len(chunks), len(text)
