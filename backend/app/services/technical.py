from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rfi


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
