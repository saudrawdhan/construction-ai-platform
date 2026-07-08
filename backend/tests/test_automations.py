from sqlalchemy import func, select

from app.models import AiSummary, Notification
from app.services.llm import MockLLM
from app.worker import tasks


async def test_daily_site_summary(db_session):
    result = await tasks.daily_site_summary(db_session)
    assert result["delayed_projects"] == 31
    assert result["notified"] >= 1
    summaries = await db_session.scalar(
        select(func.count()).select_from(AiSummary).where(
            AiSummary.summary_type == "daily_site_digest"
        )
    )
    assert summaries >= 1


async def test_overdue_rfi_reminder_notifies(db_session):
    result = await tasks.overdue_rfi_reminder(db_session)
    assert result["overdue_rfis"] == 172
    assert result["notified"] >= 1
    notifications = await db_session.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.category == "automation"
        )
    )
    assert notifications >= 1


async def test_pending_pr_alert(db_session):
    result = await tasks.pending_pr_alert(db_session)
    assert result["pending_prs"] == 1098
    assert result["notified"] >= 1


async def test_weekly_executive_report_stores_summary(db_session):
    result = await tasks.weekly_executive_report(db_session, MockLLM())
    assert result["summary_id"] is not None
    assert result["late_purchase_orders"] == 714
    assert result["notified"] >= 1
