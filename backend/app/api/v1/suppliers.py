from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agents.workflows import supplier_risk
from app.api.deps import DbSession
from app.models import User
from app.schemas.common import Page
from app.schemas.procurement import SupplierPerformance, SupplierRead
from app.schemas.workflows import SupplierRiskAssessment
from app.security.deps import CurrentUser, require_roles
from app.security.roles import Role
from app.services import procurement as procurement_service
from app.services.llm import get_llm

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

RiskRoles = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.EXECUTIVE, Role.PROCUREMENT_OFFICER))
]


@router.post("/{supplier_id}/risk-assessment", response_model=SupplierRiskAssessment)
async def assess_supplier_risk(
    supplier_id: int, db: DbSession, _: RiskRoles
) -> SupplierRiskAssessment:
    assessment = await supplier_risk.run(db, supplier_id=supplier_id, llm=get_llm())
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
