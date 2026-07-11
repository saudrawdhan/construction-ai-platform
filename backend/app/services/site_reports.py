from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyActivity, SiteReport
from app.schemas.site_reports import SiteReportCreate, SiteReportUpdate


async def create_site_report(db: AsyncSession, payload: SiteReportCreate) -> SiteReport:
    report = SiteReport(**payload.model_dump())
    db.add(report)
    await db.flush()
    return report


async def update_site_report(
    db: AsyncSession, report_id: int, payload: SiteReportUpdate
) -> SiteReport | None:
    report = await db.get(SiteReport, report_id)
    if report is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, field, value)
    await db.flush()
    return report


async def delete_site_report(db: AsyncSession, report_id: int) -> bool:
    report = await db.get(SiteReport, report_id)
    if report is None:
        return False
    await db.delete(report)
    await db.flush()
    return True


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
