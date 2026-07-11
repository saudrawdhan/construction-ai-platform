"""The synthetic demo-data generator (scripts/seed_demo_data.py).

Runs against the rolled-back test session with force=True (the test database already holds seeded
projects), so it exercises the generation logic without persisting anything.
"""

from sqlalchemy import func, select

from app.models import Project, PurchaseOrder
from scripts.seed_demo_data import DemoDataExists, seed_demo


async def test_seed_demo_creates_a_coherent_portfolio(db_session):
    counts = await seed_demo(db_session, force=True)

    # Eight demo projects, each with its own children.
    assert counts["projects"] == 8
    for entity in ("rfis", "meetings", "site_reports", "change_orders", "purchase_requests"):
        assert counts[entity] > 0, entity
    assert counts["purchase_orders"] > 0

    demo = await db_session.scalar(
        select(Project).where(Project.project_code == "DEMO-P01")
    )
    assert demo is not None
    assert demo.client_id is not None  # client resolved/created and linked

    # Some purchase orders are late and some on time, so supplier performance has signal to show.
    late = await db_session.scalar(
        select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.is_late.is_(True))
    )
    assert late > 0


async def test_seed_demo_refuses_non_empty_database_without_force(db_session):
    # The test database already contains the seeded projects, so the guard must trip.
    try:
        await seed_demo(db_session, force=False)
    except DemoDataExists:
        return
    raise AssertionError("expected DemoDataExists on a non-empty database")


async def test_seed_demo_is_deterministic(db_session):
    first = await seed_demo(db_session, force=True)
    # A second run reuses the same project codes/supplier names, so nothing new is created.
    second = await seed_demo(db_session, force=True)
    assert first["projects"] == 8
    assert second["projects"] == 0
