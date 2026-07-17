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

from app.agents.workflows import pr_review
from app.api.deps import DbSession
from app.api.v1.import_helpers import handle_tabular_import
from app.models import User
from app.schemas.common import Page
from app.schemas.imports import ImportReport
from app.schemas.procurement import (
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
    PurchaseRequestCreate,
    PurchaseRequestRead,
    PurchaseRequestUpdate,
)
from app.schemas.workflows import PRAnalyzeRequest, PurchaseRequestReview
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import imports as imports_service
from app.services import procurement as procurement_service
from app.services.llm import get_llm

router = APIRouter(prefix="/procurement", tags=["procurement"])

ProcurementRoles = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.PROCUREMENT_OFFICER, Role.PROJECT_MANAGER))
]

PURCHASE_REQUEST_TEMPLATE = (
    "project_code,request_no,material_category,specification,required_delivery_date\n"
    "PRJ-0100,PR-001,Steel,Grade 60 rebar 16mm,2026-03-01\n"
)

PURCHASE_ORDER_TEMPLATE = (
    "request_no,supplier_name,po_number,issue_date,promised_delivery,actual_delivery,status,"
    "delay_root_cause\n"
    "PR-001,Al-Rashid Steel Trading,PO-001,2026-03-05,2026-03-20,,Issued,\n"
)


@router.post("/purchase-requests/analyze", response_model=PurchaseRequestReview)
async def analyze_purchase_request(
    payload: PRAnalyzeRequest, db: DbSession, _: ProcurementRoles
) -> PurchaseRequestReview:
    review = await pr_review.run(db, pr_id=payload.pr_id, llm=get_llm())
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Purchase request not found")
    await db.commit()
    return review


@router.post(
    "/purchase-requests", response_model=PurchaseRequestRead, status_code=status.HTTP_201_CREATED
)
async def create_purchase_request(
    payload: PurchaseRequestCreate, db: DbSession, _: ProcurementRoles
) -> PurchaseRequestRead:
    request = await procurement_service.create_purchase_request(db, payload)
    await db.commit()
    await db.refresh(request)
    return PurchaseRequestRead.model_validate(request)


@router.get("/purchase-requests/import/template")
async def purchase_request_import_template(_: ProcurementRoles) -> Response:
    return Response(
        content=PURCHASE_REQUEST_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=purchase_requests_template.csv"},
    )


@router.post("/purchase-requests/import", response_model=ImportReport)
async def import_purchase_requests(
    db: DbSession,
    _: ProcurementRoles,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Form()] = False,
) -> ImportReport:
    resolve = await imports_service.project_code_resolver(db)
    return await handle_tabular_import(
        db,
        file,
        dry_run,
        schema=PurchaseRequestCreate,
        create=procurement_service.create_purchase_request,
        resolve=resolve,
    )


@router.post(
    "/purchase-orders", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED
)
async def create_purchase_order(
    payload: PurchaseOrderCreate, db: DbSession, _: ProcurementRoles
) -> PurchaseOrderRead:
    order = await procurement_service.create_purchase_order(db, payload)
    await db.commit()
    await db.refresh(order)
    return PurchaseOrderRead.model_validate(order)


@router.get("/purchase-orders/import/template")
async def purchase_order_import_template(_: ProcurementRoles) -> Response:
    return Response(
        content=PURCHASE_ORDER_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=purchase_orders_template.csv"},
    )


@router.post("/purchase-orders/import", response_model=ImportReport)
async def import_purchase_orders(
    db: DbSession,
    _: ProcurementRoles,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Form()] = False,
) -> ImportReport:
    resolve = await imports_service.purchase_order_resolver(db)
    return await handle_tabular_import(
        db,
        file,
        dry_run,
        schema=PurchaseOrderCreate,
        create=procurement_service.create_purchase_order,
        resolve=resolve,
    )


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


@router.patch("/purchase-requests/{pr_id}", response_model=PurchaseRequestRead)
async def update_purchase_request(
    pr_id: int, payload: PurchaseRequestUpdate, db: DbSession, _: ProcurementRoles
) -> PurchaseRequestRead:
    pr = await procurement_service.update_purchase_request(db, pr_id, payload)
    if pr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Purchase request not found")
    await db.commit()
    await db.refresh(pr)
    return PurchaseRequestRead.model_validate(pr)


@router.delete("/purchase-requests/{pr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase_request(
    pr_id: int, db: DbSession, _: ProcurementRoles
) -> None:
    if not await procurement_service.delete_purchase_request(db, pr_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Purchase request not found")
    await db.commit()


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


@router.patch("/purchase-orders/{po_id}", response_model=PurchaseOrderRead)
async def update_purchase_order(
    po_id: int, payload: PurchaseOrderUpdate, db: DbSession, _: ProcurementRoles
) -> PurchaseOrderRead:
    po = await procurement_service.update_purchase_order(db, po_id, payload)
    if po is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    await db.commit()
    await db.refresh(po)
    return PurchaseOrderRead.model_validate(po)


@router.delete("/purchase-orders/{po_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase_order(po_id: int, db: DbSession, _: ProcurementRoles) -> None:
    if not await procurement_service.delete_purchase_order(db, po_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    await db.commit()
