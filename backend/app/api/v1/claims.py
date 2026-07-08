from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession
from app.schemas.commercial import ClaimEvidenceChain, ClaimRead
from app.schemas.common import Page
from app.security.deps import CurrentUser
from app.services import commercial as commercial_service

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("", response_model=Page[ClaimRead])
async def list_claims(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    project_id: int | None = None,
    status: str | None = None,
    claim_type: str | None = None,
) -> Page[ClaimRead]:
    items, total = await commercial_service.list_claims(
        db, page=page, size=size, project_id=project_id, status=status, claim_type=claim_type
    )
    return Page.build([ClaimRead.model_validate(c) for c in items], total, page, size)


@router.get("/{claim_id}", response_model=ClaimRead)
async def get_claim(claim_id: int, db: DbSession, _: CurrentUser) -> ClaimRead:
    claim = await commercial_service.get_claim(db, claim_id)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return ClaimRead.model_validate(claim)


@router.get("/{claim_id}/evidence", response_model=ClaimEvidenceChain)
async def get_claim_evidence(
    claim_id: int, db: DbSession, _: CurrentUser
) -> ClaimEvidenceChain:
    chain = await commercial_service.claim_evidence_chain(db, claim_id)
    if chain is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return chain
