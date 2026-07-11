from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from app.api.deps import DbSession
from app.api.v1.import_helpers import handle_tabular_import
from app.models import User
from app.schemas.commercial import ClaimCreate, ClaimEvidenceChain, ClaimRead, ClaimUpdate
from app.schemas.common import Page
from app.schemas.imports import ImportReport
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import commercial as commercial_service
from app.services import imports as imports_service

router = APIRouter(prefix="/claims", tags=["claims"])

ManageRoles = Annotated[User, Depends(require_roles(Role.ADMIN, Role.PROJECT_MANAGER))]

CLAIM_TEMPLATE = (
    "project_code,claim_number,claim_type,amount,narrative\n"
    "PRJ-0100,CLM-001,Cost,500000,Additional works due to unforeseen ground conditions\n"
)


@router.post("", response_model=ClaimRead, status_code=status.HTTP_201_CREATED)
async def create_claim(payload: ClaimCreate, db: DbSession, _: ManageRoles) -> ClaimRead:
    claim = await commercial_service.create_claim(db, payload)
    await db.commit()
    await db.refresh(claim)
    return ClaimRead.model_validate(claim)


@router.get("/import/template")
async def claim_import_template(_: ManageRoles) -> Response:
    return Response(
        content=CLAIM_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=claims_template.csv"},
    )


@router.post("/import", response_model=ImportReport)
async def import_claims(
    db: DbSession,
    _: ManageRoles,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Form()] = False,
) -> ImportReport:
    resolve = await imports_service.project_code_resolver(db)
    return await handle_tabular_import(
        db,
        file,
        dry_run,
        schema=ClaimCreate,
        create=commercial_service.create_claim,
        resolve=resolve,
    )


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


@router.patch("/{claim_id}", response_model=ClaimRead)
async def update_claim(
    claim_id: int, payload: ClaimUpdate, db: DbSession, _: ManageRoles
) -> ClaimRead:
    claim = await commercial_service.update_claim(db, claim_id, payload)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Claim not found")
    await db.commit()
    await db.refresh(claim)
    return ClaimRead.model_validate(claim)


@router.delete("/{claim_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_claim(claim_id: int, db: DbSession, _: ManageRoles) -> None:
    if not await commercial_service.delete_claim(db, claim_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Claim not found")
    await db.commit()


@router.get("/{claim_id}/evidence", response_model=ClaimEvidenceChain)
async def get_claim_evidence(
    claim_id: int, db: DbSession, _: CurrentUser
) -> ClaimEvidenceChain:
    chain = await commercial_service.claim_evidence_chain(db, claim_id)
    if chain is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return chain
