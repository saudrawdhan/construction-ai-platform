from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agents.memory_extractor import MemoryExtractor
from app.api.deps import DbSession
from app.models import User
from app.schemas.common import Page
from app.schemas.memory import (
    MemoryCreate,
    MemoryExtractRequest,
    MemoryExtractResponse,
    MemoryRead,
    MemorySearchHit,
    MemorySearchResponse,
)
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import audit as audit_service
from app.services import memory as memory_service
from app.services.embeddings import get_embedder
from app.services.llm import get_llm

router = APIRouter(prefix="/memory", tags=["memory"])

Contributors = Annotated[
    User,
    Depends(
        require_roles(
            Role.ADMIN, Role.EXECUTIVE, Role.PROJECT_MANAGER, Role.SITE_ENGINEER,
            Role.PROCUREMENT_OFFICER, Role.QA_QC,
        )
    ),
]


@router.post("/create", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
async def create_memory(payload: MemoryCreate, db: DbSession, user: Contributors) -> MemoryRead:
    memory = await memory_service.create_memory(
        db, get_embedder(), payload, created_by="user"
    )
    await db.commit()
    await db.refresh(memory)
    return MemoryRead.model_validate(memory)


@router.get("/search", response_model=MemorySearchResponse)
async def search_memory(
    db: DbSession,
    _: CurrentUser,
    q: Annotated[str, Query(min_length=2)],
    k: Annotated[int, Query(ge=1, le=50)] = 5,
    project_id: int | None = None,
    category: str | None = None,
) -> MemorySearchResponse:
    results = await memory_service.search_memories(
        db, get_embedder(), query=q, k=k, project_id=project_id, category=category
    )
    hits = [
        MemorySearchHit(memory=MemoryRead.model_validate(memory), score=score)
        for memory, score in results
    ]
    return MemorySearchResponse(query=q, count=len(hits), results=hits)


@router.post("/extract", response_model=MemoryExtractResponse)
async def extract_memory(
    payload: MemoryExtractRequest, db: DbSession, user: Contributors
) -> MemoryExtractResponse:
    extractor = MemoryExtractor(get_llm())
    result = await extractor.extract(text=payload.text)

    stored: list[MemoryRead] = []
    if payload.store:
        embedder = get_embedder()
        for item in result.memories:
            created = await memory_service.create_memory(
                db,
                embedder,
                MemoryCreate(
                    project_id=payload.project_id,
                    category=item.category,
                    summary=item.summary,
                    detail=item.detail,
                    source_type=payload.source_type,
                    source_id=payload.source_id,
                    source_excerpt=payload.text[:500],
                    confidence=item.confidence_score,
                ),
                created_by="agent",
            )
            stored.append(MemoryRead.model_validate(created))

    await audit_service.log_ai_call(
        db,
        workflow="memory_extraction",
        provider=result.provider,
        model=result.model,
        user_id=user.id,
        source_ids={"source_type": payload.source_type, "source_id": payload.source_id},
        output_excerpt="; ".join(m.summary for m in result.memories),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
    await db.commit()
    return MemoryExtractResponse(
        provider=result.provider,
        model=result.model,
        extracted=result.memories,
        stored=stored,
    )


@router.get("", response_model=Page[MemoryRead])
async def list_memories(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    project_id: int | None = None,
    category: str | None = None,
) -> Page[MemoryRead]:
    items, total = await memory_service.list_memories(
        db, page=page, size=size, project_id=project_id, category=category
    )
    return Page.build([MemoryRead.model_validate(m) for m in items], total, page, size)


@router.get("/{memory_id}", response_model=MemoryRead)
async def get_memory(memory_id: int, db: DbSession, _: CurrentUser) -> MemoryRead:
    memory = await memory_service.get_memory(db, memory_id)
    if memory is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return MemoryRead.model_validate(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(memory_id: int, db: DbSession, user: Contributors) -> None:
    deleted = await memory_service.delete_memory(db, memory_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Memory not found")
    await db.commit()
