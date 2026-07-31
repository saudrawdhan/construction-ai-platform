import uuid


async def test_list_projects_is_paginated(client, admin_headers):
    response = await client.get("/api/v1/projects?size=5", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 60
    assert body["size"] == 5
    assert len(body["items"]) == 5
    assert body["pages"] == 12


async def test_list_projects_filter_by_status(client, admin_headers):
    response = await client.get("/api/v1/projects?status=Delayed", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert all(item["status"] == "Delayed" for item in body["items"])


async def test_get_project_by_id(client, admin_headers):
    response = await client.get("/api/v1/projects/1", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == 1


async def test_get_missing_project_returns_404(client, admin_headers):
    response = await client.get("/api/v1/projects/999999", headers=admin_headers)
    assert response.status_code == 404


async def test_requires_authentication(client):
    response = await client.get("/api/v1/projects")
    assert response.status_code == 401


async def test_create_project_as_admin(client, admin_headers):
    payload = {
        "project_code": f"TST-{uuid.uuid4().hex[:8]}",
        "project_name": "Integration Test Project",
        "project_type": "Tower",
        "client_name": "Integration Test Client",
        "city": "Riyadh",
        "status": "Planned",
        "budget": "1000000.00",
    }
    response = await client.post("/api/v1/projects", json=payload, headers=admin_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 60
    assert body["client_id"] is not None


async def test_create_project_forbidden_for_viewer(client, viewer_headers):
    payload = {
        "project_code": f"TST-{uuid.uuid4().hex[:8]}",
        "project_name": "Should Fail",
        "project_type": "Tower",
        "client_name": "Nope",
        "city": "Riyadh",
        "status": "Planned",
        "budget": "1000000.00",
    }
    response = await client.post("/api/v1/projects", json=payload, headers=viewer_headers)
    assert response.status_code == 403


async def test_create_and_list_project_risk(client, admin_headers):
    payload = {"title": "Schedule slippage risk", "severity": "High", "owner": "PM"}
    created = await client.post(
        "/api/v1/projects/2/risks", json=payload, headers=admin_headers
    )
    assert created.status_code == 201
    assert created.json()["status"] == "Open"

    listed = await client.get("/api/v1/projects/2/risks", headers=admin_headers)
    assert listed.status_code == 200
    assert any(r["title"] == "Schedule slippage risk" for r in listed.json())


async def _new_project_id(client, headers) -> int:
    """A project created inside the test transaction, so register assertions hold exact counts
    regardless of what the demo seed puts in these tables."""
    response = await client.post(
        "/api/v1/projects",
        json={
            "project_code": f"TST-{uuid.uuid4().hex[:8]}",
            "project_name": "Register Test Project",
            "project_type": "Building",
            "client_name": "Test Client",
            "city": "Riyadh",
            "status": "Active",
            "budget": "1000000.00",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_project_issues_create_and_list(client, admin_headers):
    project_id = await _new_project_id(client, admin_headers)
    created = await client.post(
        f"/api/v1/projects/{project_id}/issues",
        json={"title": "Access road blocked", "description": "Blocking deliveries.",
              "owner": "Eng. Salem"},
        headers=admin_headers,
    )
    assert created.status_code == 201
    assert created.json()["status"] == "Open"

    listed = await client.get(f"/api/v1/projects/{project_id}/issues", headers=admin_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["title"] == "Access road blocked"
    assert body[0]["owner"] == "Eng. Salem"


async def test_project_milestones_sort_by_planned_date_with_undated_last(client, admin_headers):
    project_id = await _new_project_id(client, admin_headers)
    for name, planned in [
        ("Handover", "2026-12-01"),
        ("Undated review", None),
        ("Foundation complete", "2026-03-15"),
    ]:
        response = await client.post(
            f"/api/v1/projects/{project_id}/milestones",
            json={"name": name, "planned_date": planned},
            headers=admin_headers,
        )
        assert response.status_code == 201

    listed = await client.get(f"/api/v1/projects/{project_id}/milestones", headers=admin_headers)
    names = [m["name"] for m in listed.json()]
    assert names == ["Foundation complete", "Handover", "Undated review"]
    assert listed.json()[0]["status"] == "Pending"


async def test_project_decisions_are_readable_at_project_level(client, admin_headers):
    # 535 decisions were seeded and written by the meeting-summary workflow, but were reachable
    # only one meeting at a time — a project's decision history had no endpoint at all.
    response = await client.get("/api/v1/projects/3/decisions", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert all(d["project_id"] == 3 for d in body)
    assert body[0]["decision_text"]
    assert body[0]["meeting_id"]


async def test_project_registers_404_for_unknown_project(client, admin_headers):
    for register in ("issues", "milestones", "decisions"):
        response = await client.get(
            f"/api/v1/projects/999999/{register}", headers=admin_headers
        )
        assert response.status_code == 404, register


async def test_project_register_writes_forbidden_for_viewer(client, viewer_headers):
    # Reads are open to any authenticated user and writes are project-manager tier, matching the
    # risk register these mirror.
    for register, payload in (
        ("issues", {"title": "x"}),
        ("milestones", {"name": "x"}),
    ):
        response = await client.post(
            f"/api/v1/projects/1/{register}", json=payload, headers=viewer_headers
        )
        assert response.status_code == 403, register
    for register in ("issues", "milestones", "decisions"):
        response = await client.get(f"/api/v1/projects/1/{register}", headers=viewer_headers)
        assert response.status_code == 200, register
