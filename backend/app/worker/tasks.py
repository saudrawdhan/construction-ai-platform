"""Scheduled-automation task logic. Pure async functions that take a session so they are
unit-testable without the cron runtime. They persist ai_summaries and role-targeted
notifications; the arq wrapper opens the session and commits. These jobs run in mock LLM mode so
recurring automation never incurs LLM API cost.
"""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.workflows import executive_report as executive_workflow
from app.models import AiSummary, Notification, Project, PurchaseRequest, Rfi, SiteReport, User
from app.schemas.workflows import ExecutiveReportRequest
from app.security.roles import Role
from app.services.llm import LLMClient

_PENDING_PR = ("Under Review", "Pending Clarification", "Needs Rework", "Returned to Requester")


async def _notify_roles(
    db: AsyncSession,
    roles: list[Role],
    *,
    title: str,
    body: str,
    category: str,
    project_id: int | None = None,
) -> int:
    """Notify every active holder of the given roles.

    ``category`` names the area the alert is about so the notification bell can send the reader to
    the page that answers it. Every alert previously carried the same "automation" label, which
    left the reader knowing something happened but with nowhere to go and no way to tell an
    overdue RFI apart from a pending purchase request.
    """
    users = await db.scalars(
        select(User).where(
            User.role.in_([role.value for role in roles]), User.is_active.is_(True)
        )
    )
    count = 0
    for user in users:
        db.add(
            Notification(
                user_id=user.id, project_id=project_id, channel="in_app",
                title=title, body=body, category=category,
            )
        )
        count += 1
    return count


async def daily_site_summary(db: AsyncSession) -> dict:
    today = date.today()
    since = today - timedelta(days=1)
    recent_reports = await db.scalar(
        select(func.count()).select_from(SiteReport).where(SiteReport.report_date >= since)
    )
    delayed = await db.scalar(
        select(func.count()).select_from(Project).where(
            Project.status.in_(["Delayed", "On Hold"])
        )
    )
    content = (
        f"Daily site digest {today}: {recent_reports} site report(s) in the last day; "
        f"{delayed} project(s) delayed or on hold."
    )
    db.add(
        AiSummary(
            summary_type="daily_site_digest", period_start=since, period_end=today,
            content=content,
            structured_output={"recent_site_reports": recent_reports, "delayed_projects": delayed},
        )
    )
    notified = await _notify_roles(
        db, [Role.EXECUTIVE, Role.PROJECT_MANAGER], title="Daily site digest", body=content,
        category="site_report",
    )
    return {
        "recent_site_reports": recent_reports,
        "delayed_projects": delayed,
        "notified": notified,
    }


async def overdue_rfi_reminder(db: AsyncSession) -> dict:
    today = date.today()
    overdue = await db.scalar(
        select(func.count()).select_from(Rfi).where(
            Rfi.status != "Closed", Rfi.required_date < today
        )
    )
    notified = 0
    if overdue:
        body = f"{overdue} RFI(s) are overdue and may be blocking execution. Please expedite."
        notified = await _notify_roles(
            db, [Role.PROJECT_MANAGER, Role.SITE_ENGINEER], title="Overdue RFI reminder",
            body=body, category="rfi",
        )
    return {"overdue_rfis": int(overdue or 0), "notified": notified}


async def pending_pr_alert(db: AsyncSession) -> dict:
    pending = await db.scalar(
        select(func.count()).select_from(PurchaseRequest).where(
            PurchaseRequest.status.in_(_PENDING_PR)
        )
    )
    notified = 0
    if pending:
        body = f"{pending} purchase request(s) are awaiting procurement action."
        notified = await _notify_roles(
            db, [Role.PROCUREMENT_OFFICER], title="Pending purchase requests", body=body,
            category="procurement",
        )
    return {"pending_prs": int(pending or 0), "notified": notified}


async def weekly_executive_report(db: AsyncSession, llm: LLMClient) -> dict:
    report = await executive_workflow.run(db, payload=ExecutiveReportRequest(store=True), llm=llm)
    notified = await _notify_roles(
        db, [Role.EXECUTIVE, Role.ADMIN], title="Weekly executive report", category="report",
        body=report.narrative[:400],
    )
    return {
        "summary_id": report.summary_id,
        "overdue_rfis": report.overdue_rfis,
        "late_purchase_orders": report.late_purchase_orders,
        "notified": notified,
    }
