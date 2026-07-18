import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import DbSession
from app.models import Project, User
from app.schemas.common import Page
from app.schemas.documents import DocumentRead, DocumentUploadResult, GeneratedDocumentRead
from app.schemas.search import SearchResponse
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import documents as document_service
from app.services.document_ingest import (
    MAX_UPLOAD_BYTES,
    EmptyDocument,
    UnsupportedDocument,
    ingest_upload,
)
from app.services.embeddings import get_embedder
from app.services.retrieval import hybrid_search

router = APIRouter(prefix="/documents", tags=["documents"])

UploadRoles = Annotated[
    User,
    Depends(
        require_roles(
            Role.ADMIN, Role.EXECUTIVE, Role.PROJECT_MANAGER, Role.SITE_ENGINEER,
            Role.PROCUREMENT_OFFICER, Role.QA_QC,
        )
    ),
]


@router.get("/search", response_model=SearchResponse)
async def search_documents(
    db: DbSession,
    _: CurrentUser,
    q: Annotated[str, Query(min_length=2)],
    k: Annotated[int, Query(ge=1, le=50)] = 8,
    project_id: int | None = None,
) -> SearchResponse:
    hits = await hybrid_search(db, get_embedder(), query=q, k=k, project_id=project_id)
    return SearchResponse(query=q, count=len(hits), results=hits)


@router.post("/upload", response_model=DocumentUploadResult, status_code=status.HTTP_201_CREATED)
async def upload_document(
    db: DbSession,
    _: UploadRoles,
    file: Annotated[UploadFile, File()],
    project_id: Annotated[int, Form()],
    doc_type: Annotated[str, Form()] = "uploaded",
    title: Annotated[str | None, Form()] = None,
) -> DocumentUploadResult:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")

    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds the 10 MB upload limit"
        )

    embedder = get_embedder()
    try:
        document, chunks, characters = await ingest_upload(
            db,
            embedder,
            project_id=project_id,
            doc_type=doc_type,
            title=(title or file.filename or "Untitled document").strip(),
            filename=file.filename or "",
            data=data,
        )
    except EmptyDocument as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except UnsupportedDocument as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc

    await db.commit()
    return DocumentUploadResult(
        document_id=document.id,
        project_id=project_id,
        title=document.title,
        doc_type=document.doc_type,
        characters=characters,
        chunks_indexed=chunks,
        embedding_provider=embedder.provider,
    )


@router.get("", response_model=Page[DocumentRead])
async def list_documents(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    project_id: int | None = None,
    doc_type: str | None = None,
) -> Page[DocumentRead]:
    items, total = await document_service.list_documents(
        db, page=page, size=size, project_id=project_id, doc_type=doc_type
    )
    return Page.build([DocumentRead.model_validate(d) for d in items], total, page, size)


@router.get("/generated", response_model=Page[GeneratedDocumentRead])
async def list_generated_documents(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    project_id: int | None = None,
    doc_type: str | None = None,
) -> Page[GeneratedDocumentRead]:
    items, total = await document_service.list_generated_documents(
        db, page=page, size=size, project_id=project_id, doc_type=doc_type
    )
    return Page.build(
        [GeneratedDocumentRead.model_validate(d) for d in items], total, page, size
    )


@router.get("/generated/{document_id}", response_model=GeneratedDocumentRead)
async def get_generated_document(
    document_id: int, db: DbSession, _: CurrentUser
) -> GeneratedDocumentRead:
    document = await document_service.get_generated_document(db, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Generated document not found")
    return GeneratedDocumentRead.model_validate(document)


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: int, db: DbSession, _: CurrentUser
) -> DocumentRead:
    document = await document_service.get_document(db, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentRead.model_validate(document)


@router.get("/{document_id}/download")
async def download_document(document_id: int, db: DbSession, _: CurrentUser) -> FileResponse:
    document = await document_service.get_document(db, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.storage_path is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No original file was stored for this document",
        )
    path = Path(document.storage_path)
    if not await asyncio.to_thread(path.is_file):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Stored file is missing")
    return FileResponse(path, filename=document.original_filename or path.name)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: int, db: DbSession, _: UploadRoles) -> None:
    deleted = await document_service.delete_document(db, document_id)
    if deleted is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    await db.commit()
