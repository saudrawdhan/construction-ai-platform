from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyActivity, SiteReport


async def list_site_reports(
    db: AsyncSession,
    *,
    page: int,
    size: int,
    project_id: int | None = None,
) -> tuple[list[SiteReport], int]:
    query = select(SiteReport)
    if project_id:
        query = query.where(SiteReport.project_id == project_id)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(SiteReport.report_date.desc()).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def get_site_report(db: AsyncSession, report_id: int) -> SiteReport | None:
    return await db.get(SiteReport, report_id)


async def list_activities(db: AsyncSession, report_id: int) -> list[DailyActivity]:
    rows = await db.scalars(
        select(DailyActivity)
        .where(DailyActivity.site_report_id == report_id)
        .order_by(DailyActivity.id)
    )
    return list(rows)
