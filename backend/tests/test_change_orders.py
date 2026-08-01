from sqlalchemy import select

from app.models import ChangeOrder, Project


async def test_list_change_orders_total(client, admin_headers):
    response = await client.get("/api/v1/change-orders?size=5", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 120


async def test_filter_change_orders_by_status(client, admin_headers):
    response = await client.get("/api/v1/change-orders?status=Approved", headers=admin_headers)
    assert response.status_code == 200
    assert all(c["status"] == "Approved" for c in response.json()["items"])


async def test_get_change_order(client, admin_headers):
    response = await client.get("/api/v1/change-orders/1", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["co_number"] == "CO-00001"


async def test_missing_change_order_404(client, admin_headers):
    response = await client.get("/api/v1/change-orders/999999", headers=admin_headers)
    assert response.status_code == 404


async def _co_id(client, headers) -> int:
    response = await client.get("/api/v1/change-orders?size=1", headers=headers)
    return response.json()["items"][0]["id"]


async def test_change_order_carries_cause_and_schedule_impact(client, admin_headers):
    # Brief module 5 asks a change order to "connect to causes, estimate impact". It previously
    # recorded only co_number/description/value/status, so neither question could be answered.
    co_id = await _co_id(client, admin_headers)
    response = await client.get(f"/api/v1/change-orders/{co_id}", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert "cause_category" in body
    assert "cause_rfi_id" in body
    assert "schedule_impact_days" in body


async def test_change_order_cause_and_impact_round_trip(client, admin_headers):
    created = await client.post(
        "/api/v1/change-orders",
        json={
            "project_id": 1, "co_number": "CO-CAUSE-TEST", "description": "Scope change.",
            "value": "125000.00", "status": "Pending",
            "cause_category": "site_condition",
            "cause_description": "Rock encountered below the design founding level.",
            "schedule_impact_days": 14,
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["cause_category"] == "site_condition"
    assert body["schedule_impact_days"] == 14

    patched = await client.patch(
        f"/api/v1/change-orders/{body['id']}",
        json={"schedule_impact_days": 21},
        headers=admin_headers,
    )
    assert patched.json()["schedule_impact_days"] == 21


async def test_change_order_impact_rolls_up_cost_programme_and_cause(client, admin_headers):
    # The per-record fields answer "what caused this one"; a project manager asks for the total.
    response = await client.get("/api/v1/change-orders/impact/1", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == 1
    assert body["change_order_count"] >= 1
    assert float(body["total_value"]) >= float(body["approved_value"])
    assert body["total_schedule_impact_days"] >= 0
    assert isinstance(body["by_cause"], dict) and body["by_cause"]
    assert body["caused_by_rfi_count"] <= body["change_order_count"]


async def test_change_order_impact_of_a_project_with_none_is_zeroed(
    client, admin_headers, db_session
):
    # This used to ask for project 999999, which is not "a project with none" but a project that
    # does not exist — and it therefore locked in a zeroed commercial roll-up as the answer for an
    # unknown id, which reads as "this project has no change orders". The project is now looked up
    # rather than hardcoded, so the test measures what its name says and does not depend on which
    # ids the dataset happens to use.
    project_id = await db_session.scalar(
        select(Project.id)
        .outerjoin(ChangeOrder, ChangeOrder.project_id == Project.id)
        .where(ChangeOrder.id.is_(None))
        .limit(1)
    )
    assert project_id is not None, "expected at least one project with no change orders"

    response = await client.get(
        f"/api/v1/change-orders/impact/{project_id}", headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["change_order_count"] == 0
    assert float(body["total_value"]) == 0
    assert body["by_cause"] == {}
