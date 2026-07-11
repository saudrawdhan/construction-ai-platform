from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rfi
from app.schemas.technical import RfiCreate, RfiUpdate


async def create_rfi(db: AsyncSession, payload: RfiCreate) -> Rfi:
    rfi = Rfi(**payload.model_dump())
    db.add(rfi)
    await db.flush()
    return rfi


async def update_rfi(db: AsyncSession, rfi_id: int, payload: RfiUpdate) -> Rfi | None:
    rfi = await db.get(Rfi, rfi_id)
    if rfi is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rfi, field, value)
    await db.flush()
    return rfi


async def delete_rfi(db: AsyncSession, rfi_id: int) -> bool:
    rfi = await db.get(Rfi, rfi_id)
    if rfi is None:
        return False
    await db.delete(rfi)
    await db.flush()
    return True


async def list_rfis(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    project_id: int | None = None,
    status: str | None = None,
    discipline: str | None = None,
    overdue: bool = False,
) -> tuple[list[Rfi], int]:
    query = select(Rfi)
    if project_id:
        query = query.where(Rfi.project_id == project_id)
    if status:
        query = query.where(Rfi.status == status)
    if discipline:
        query = query.where(Rfi.discipline == discipline)
    if overdue:
        query = query.where(Rfi.status != "Closed", Rfi.required_date < func.current_date())

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(Rfi.required_date).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def get_rfi(db: AsyncSession, rfi_id: int) -> Rfi | None:
    return await db.get(Rfi, rfi_id)
