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
