from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ncr, PurchaseOrder, PurchaseRequest, Supplier
from app.schemas.procurement import (
    DelayCause,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseRequestCreate,
    PurchaseRequestUpdate,
    SupplierCreate,
    SupplierPerformance,
    SupplierUpdate,
)


async def list_suppliers(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    category: str | None = None,
    city: str | None = None,
    status: str | None = None,
) -> tuple[list[Supplier], int]:
    query = select(Supplier)
    if category:
        query = query.where(Supplier.category == category)
    if city:
        query = query.where(Supplier.city == city)
    if status:
        query = query.where(Supplier.status == status)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(query.order_by(Supplier.id).offset((page - 1) * size).limit(size))
    return list(rows), int(total or 0)


async def get_supplier(db: AsyncSession, supplier_id: int) -> Supplier | None:
    return await db.get(Supplier, supplier_id)


async def create_supplier(db: AsyncSession, payload: SupplierCreate) -> Supplier:
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    await db.flush()
    return supplier


async def update_supplier(
    db: AsyncSession, supplier_id: int, payload: SupplierUpdate
) -> Supplier | None:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    await db.flush()
    return supplier


async def delete_supplier(db: AsyncSession, supplier_id: int) -> bool:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        return False
    await db.delete(supplier)
    await db.flush()
    return True


async def supplier_performance(
    db: AsyncSession, supplier_id: int
) -> SupplierPerformance | None:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        return None

    orders = select(PurchaseOrder).where(PurchaseOrder.supplier_id == supplier_id).subquery()
    total = await db.scalar(select(func.count()).select_from(orders)) or 0
    late = (
        await db.scalar(
            select(func.count())
            .select_from(PurchaseOrder)
            .where(PurchaseOrder.supplier_id == supplier_id, PurchaseOrder.is_late.is_(True))
        )
        or 0
    )
    total_delay = (
        await db.scalar(
            select(func.coalesce(func.sum(PurchaseOrder.delay_days), 0)).where(
                PurchaseOrder.supplier_id == supplier_id
            )
        )
        or 0
    )
    ncr_count = (
        await db.scalar(
            select(func.count()).select_from(Ncr).where(Ncr.supplier_id == supplier_id)
        )
        or 0
    )
    cause_rows = await db.execute(
        select(PurchaseOrder.delay_root_cause, func.count().label("count"))
        .where(
            PurchaseOrder.supplier_id == supplier_id,
            PurchaseOrder.is_late.is_(True),
            PurchaseOrder.delay_root_cause.is_not(None),
        )
        .group_by(PurchaseOrder.delay_root_cause)
        .order_by(func.count().desc())
        .limit(5)
    )

    return SupplierPerformance(
        supplier_id=supplier.id,
        supplier_name=supplier.supplier_name,
        total_purchase_orders=total,
        late_purchase_orders=late,
        on_time_rate=round((total - late) / total * 100, 1) if total else 0.0,
        total_delay_days=int(total_delay),
        average_delay_days_when_late=round(total_delay / late, 1) if late else 0.0,
        ncr_count=ncr_count,
        top_delay_causes=[DelayCause(cause=cause, count=count) for cause, count in cause_rows],
    )


async def list_purchase_requests(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    project_id: int | None = None,
    status: str | None = None,
    material_category: str | None = None,
    incomplete: bool = False,
) -> tuple[list[PurchaseRequest], int]:
    query = select(PurchaseRequest)
    if project_id:
        query = query.where(PurchaseRequest.project_id == project_id)
    if status:
        query = query.where(PurchaseRequest.status == status)
    if material_category:
        query = query.where(PurchaseRequest.material_category == material_category)
    if incomplete:
        query = query.where(
            (PurchaseRequest.specification.is_(None))
            | (PurchaseRequest.required_delivery_date.is_(None))
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(PurchaseRequest.id).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def get_purchase_request(db: AsyncSession, pr_id: int) -> PurchaseRequest | None:
    return await db.get(PurchaseRequest, pr_id)


async def create_purchase_request(
    db: AsyncSession, payload: PurchaseRequestCreate
) -> PurchaseRequest:
    request = PurchaseRequest(**payload.model_dump(), created_at=date.today())
    db.add(request)
    await db.flush()
    return request


async def update_purchase_request(
    db: AsyncSession, pr_id: int, payload: PurchaseRequestUpdate
) -> PurchaseRequest | None:
    request = await db.get(PurchaseRequest, pr_id)
    if request is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(request, field, value)
    await db.flush()
    return request


async def delete_purchase_request(db: AsyncSession, pr_id: int) -> bool:
    request = await db.get(PurchaseRequest, pr_id)
    if request is None:
        return False
    await db.delete(request)
    await db.flush()
    return True


async def create_purchase_order(
    db: AsyncSession, payload: PurchaseOrderCreate
) -> PurchaseOrder:
    data = payload.model_dump()
    is_late, delay_days = _lateness(data.get("promised_delivery"), data.get("actual_delivery"))
    order = PurchaseOrder(**data, is_late=is_late, delay_days=delay_days)
    db.add(order)
    await db.flush()
    return order


def _lateness(promised: date | None, actual: date | None) -> tuple[bool, int]:
    if promised and actual and actual > promised:
        return True, (actual - promised).days
    return False, 0


async def update_purchase_order(
    db: AsyncSession, po_id: int, payload: PurchaseOrderUpdate
) -> PurchaseOrder | None:
    order = await db.get(PurchaseOrder, po_id)
    if order is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(order, field, value)
    # Lateness is derived, never entered — recompute it from the resulting delivery dates.
    order.is_late, order.delay_days = _lateness(order.promised_delivery, order.actual_delivery)
    await db.flush()
    return order


async def delete_purchase_order(db: AsyncSession, po_id: int) -> bool:
    order = await db.get(PurchaseOrder, po_id)
    if order is None:
        return False
    await db.delete(order)
    await db.flush()
    return True


async def list_purchase_orders(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    project_id: int | None = None,
    supplier_id: int | None = None,
    status: str | None = None,
    is_late: bool | None = None,
) -> tuple[list[PurchaseOrder], int]:
    query = select(PurchaseOrder)
    if project_id:
        query = query.where(PurchaseOrder.project_id == project_id)
    if supplier_id:
        query = query.where(PurchaseOrder.supplier_id == supplier_id)
    if status:
        query = query.where(PurchaseOrder.status == status)
    if is_late is not None:
        query = query.where(PurchaseOrder.is_late.is_(is_late))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(PurchaseOrder.id).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def get_purchase_order(db: AsyncSession, po_id: int) -> PurchaseOrder | None:
    return await db.get(PurchaseOrder, po_id)
