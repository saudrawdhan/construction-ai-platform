from sqlalchemy import func, select

from app.models import AiSummary, Meeting, MeetingActionItem, ProjectDecision

MINUTES = """Discussion Summary:
The team reviewed procurement status and site constraints affecting the critical path.

Decisions:
- Procurement to expedite long-lead switchgear. Owner: Project Manager
- Accept partial handover of zone A. Owner: Client Representative

Actions:
- Contractor to update the recovery plan.
- QA/QC to close open NCRs.

There is a risk of delay on the MEP milestone if material delivery slips.
"""


async def test_meeting_summarize_extracts_structure(client, admin_headers):
    response = await client.post(
        "/api/v1/meetings/7/summarize", json={"notes": MINUTES}, headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["decisions"]) == 2
    assert len(body["action_items"]) == 2
    assert any("delay" in r.lower() for r in body["risks"])
    assert body["meeting_id"] is None  # not stored


async def test_meeting_summarize_store_writes_records(client, admin_headers, db_session):
    before = await db_session.scalar(select(func.count()).select_from(Meeting))
    response = await client.post(
        "/api/v1/meetings/7/summarize",
        json={"notes": MINUTES, "store": True, "title": "Weekly Progress"},
        headers=admin_headers,
    )
    body = response.json()
    assert body["meeting_id"] is not None
    assert body["stored_action_items"] == 2
    assert body["stored_decisions"] == 2

    after = await db_session.scalar(select(func.count()).select_from(Meeting))
    assert after == before + 1
    actions = await db_session.scalar(
        select(func.count()).select_from(MeetingActionItem).where(
            MeetingActionItem.meeting_id == body["meeting_id"]
        )
    )
    assert actions == 2
    decisions = await db_session.scalar(
        select(func.count()).select_from(ProjectDecision).where(
            ProjectDecision.meeting_id == body["meeting_id"]
        )
    )
    assert decisions == 2


async def test_site_report_analyze(client, admin_headers):
    text = (
        "Civil works progressed on zone B and the slab was poured. "
        "Material delivery is delayed and the inspection is pending. "
        "Risk of impact on the finishing sequence. Crew of 40 on site."
    )
    response = await client.post(
        "/api/v1/site-reports/14/analyze", json={"text": text}, headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["completed_work"]
    assert body["delays"]
    assert "escalat" in body["recommended_escalation"].lower()


async def test_executive_report_aggregates_and_stores(client, admin_headers, db_session):
    response = await client.post(
        "/api/v1/reports/executive-weekly", json={"store": True}, headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["projects_total"] == 60
    assert body["overdue_rfis"] >= 1
    assert body["late_purchase_orders"] == 714
    assert len(body["highlights"]) >= 5
    assert body["summary_id"] is not None

    stored = await db_session.scalar(
        select(func.count()).select_from(AiSummary).where(
            AiSummary.summary_type == "executive_weekly"
        )
    )
    assert stored >= 1


async def test_executive_report_forbidden_for_viewer(client, viewer_headers):
    response = await client.post(
        "/api/v1/reports/executive-weekly", json={"store": False}, headers=viewer_headers
    )
    assert response.status_code == 403
