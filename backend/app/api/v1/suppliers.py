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

from app.agents.workflows import supplier_risk
from app.api.deps import DbSession, RequestLanguage
from app.api.v1.import_helpers import handle_tabular_import
from app.models import User
from app.schemas.common import Page
from app.schemas.imports import ImportReport
from app.schemas.procurement import (
    SupplierCreate,
    SupplierPerformance,
    SupplierRead,
    SupplierUpdate,
)
from app.schemas.workflows import SupplierRiskAssessment
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import procurement as procurement_service
from app.services.llm import get_llm

SUPPLIER_TEMPLATE = "supplier_name,category,city,status\nFalcon Steel Works,Steel,Riyadh,Active\n"

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

RiskRoles = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.EXECUTIVE, Role.PROCUREMENT_OFFICER))
]
ManageRoles = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.PROCUREMENT_OFFICER))
]


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    payload: SupplierCreate, db: DbSession, _: ManageRoles
) -> SupplierRead:
    supplier = await procurement_service.create_supplier(db, payload)
    await db.commit()
    await db.refresh(supplier)
    return SupplierRead.model_validate(supplier)


@router.patch("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    supplier_id: int, payload: SupplierUpdate, db: DbSession, _: ManageRoles
) -> SupplierRead:
    supplier = await procurement_service.update_supplier(db, supplier_id, payload)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    await db.commit()
    await db.refresh(supplier)
    return SupplierRead.model_validate(supplier)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(supplier_id: int, db: DbSession, _: ManageRoles) -> None:
    if not await procurement_service.delete_supplier(db, supplier_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    await db.commit()


@router.get("/import/template")
async def supplier_import_template(_: ManageRoles) -> Response:
    return Response(
        content=SUPPLIER_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=suppliers_template.csv"},
    )


@router.post("/import", response_model=ImportReport)
async def import_suppliers(
    db: DbSession,
    _: ManageRoles,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Form()] = False,
) -> ImportReport:
    return await handle_tabular_import(
        db, file, dry_run, schema=SupplierCreate, create=procurement_service.create_supplier
    )


@router.post("/{supplier_id}/risk-assessment", response_model=SupplierRiskAssessment)
async def assess_supplier_risk(
    supplier_id: int, db: DbSession, _: RiskRoles, language: RequestLanguage
) -> SupplierRiskAssessment:
    assessment = await supplier_risk.run(
        db, supplier_id=supplier_id, llm=get_llm(), language=language
    )
    if assessment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    await db.commit()
    return assessment


@router.get("", response_model=Page[SupplierRead])
async def list_suppliers(
    db: DbSession,
    _: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
    city: str | None = None,
    status: str | None = None,
) -> Page[SupplierRead]:
    items, total = await procurement_service.list_suppliers(
        db, page=page, size=size, category=category, city=city, status=status
    )
    return Page.build([SupplierRead.model_validate(s) for s in items], total, page, size)


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(supplier_id: int, db: DbSession, _: CurrentUser) -> SupplierRead:
    supplier = await procurement_service.get_supplier(db, supplier_id)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return SupplierRead.model_validate(supplier)


@router.get("/{supplier_id}/performance", response_model=SupplierPerformance)
async def get_supplier_performance(
    supplier_id: int, db: DbSession, _: CurrentUser
) -> SupplierPerformance:
    performance = await procurement_service.supplier_performance(db, supplier_id)
    if performance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return performance
