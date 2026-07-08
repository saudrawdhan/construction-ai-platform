from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agents.workflows import pr_review
from app.api.deps import DbSession
from app.models import User
from app.schemas.common import Page
from app.schemas.procurement import PurchaseOrderRead, PurchaseRequestRead
from app.schemas.workflows import PRAnalyzeRequest, PurchaseRequestReview
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import procurement as procurement_service
from app.services.llm import get_llm

router = APIRouter(prefix="/procurement", tags=["procurement"])

ProcurementRoles = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.PROCUREMENT_OFFICER, Role.PROJECT_MANAGER))
]


@router.post("/purchase-requests/analyze", response_model=PurchaseRequestReview)
async def analyze_purchase_request(
    payload: PRAnalyzeRequest, db: DbSession, _: ProcurementRoles
) -> PurchaseRequestReview:
    review = await pr_review.run(db, pr_id=payload.pr_id, llm=get_llm())
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Purchase request not found")
    await db.commit()
    return review


@router.get("/purchase-requests", response_model=Page[PurchaseRequestRead])
async def list_purchase_requests(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    project_id: int | None = None,
    status: str | None = None,
    material_category: str | None = None,
    incomplete: bool = False,
) -> Page[PurchaseRequestRead]:
    items, total = await procurement_service.list_purchase_requests(
        db,
        page=page,
        size=size,
        project_id=project_id,
        status=status,
        material_category=material_category,
        incomplete=incomplete,
    )
    return Page.build(
        [PurchaseRequestRead.model_validate(p) for p in items], total, page, size
    )


@router.get("/purchase-requests/{pr_id}", response_model=PurchaseRequestRead)
async def get_purchase_request(
    pr_id: int, db: DbSession, _: CurrentUser
) -> PurchaseRequestRead:
    pr = await procurement_service.get_purchase_request(db, pr_id)
    if pr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Purchase request not found")
    return PurchaseRequestRead.model_validate(pr)


@router.get("/purchase-orders", response_model=Page[PurchaseOrderRead])
async def list_purchase_orders(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    project_id: int | None = None,
    supplier_id: int | None = None,
    status: str | None = None,
    is_late: bool | None = None,
) -> Page[PurchaseOrderRead]:
    items, total = await procurement_service.list_purchase_orders(
        db,
        page=page,
        size=size,
        project_id=project_id,
        supplier_id=supplier_id,
        status=status,
        is_late=is_late,
    )
    return Page.build([PurchaseOrderRead.model_validate(o) for o in items], total, page, size)


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderRead)
async def get_purchase_order(
    po_id: int, db: DbSession, _: CurrentUser
) -> PurchaseOrderRead:
    po = await procurement_service.get_purchase_order(db, po_id)
    if po is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return PurchaseOrderRead.model_validate(po)
