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
            Notification.category == "rfi"
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


async def test_scheduled_alerts_carry_a_routable_category(client, admin_headers, db_session):
    # Every scheduled alert previously used the same "automation" label, so the bell could tell a
    # reader something happened but not where to go, and an overdue RFI looked identical to a
    # pending purchase request. Each alert now names the area that answers it.
    from app.services.llm import get_llm
    from app.worker import tasks

    await tasks.daily_site_summary(db_session)
    await tasks.overdue_rfi_reminder(db_session)
    await tasks.pending_pr_alert(db_session)
    await tasks.weekly_executive_report(db_session, get_llm())
    await db_session.flush()

    categories = set(
        await db_session.scalars(
            select(Notification.category).where(Notification.category.is_not(None))
        )
    )
    # The routes the bell knows how to open.
    assert {"site_report", "rfi", "procurement", "report"} & categories
    assert "automation" not in categories
