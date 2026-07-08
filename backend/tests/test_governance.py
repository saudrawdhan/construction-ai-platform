from sqlalchemy import func, select

from app.models import AiAuditLog, Notification


async def _create_approval(client, headers, action="send_external_email"):
    return await client.post(
        "/api/v1/approvals",
        json={"action_type": action, "project_id": 1, "payload": {"to": "client@x.com"},
              "risk_level": "high"},
        headers=headers,
    )


async def test_create_approval_is_pending(client, admin_headers):
    response = await _create_approval(client, admin_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["requested_by"] == "test-admin@construction-ops.com"


async def test_viewer_cannot_create_approval(client, viewer_headers):
    response = await _create_approval(client, viewer_headers)
    assert response.status_code == 403


async def test_approval_lifecycle_and_notification(client, admin_headers, db_session):
    created = await _create_approval(client, admin_headers)
    approval_id = created.json()["id"]

    approved = await client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"note": "Authorized by PM"}, headers=admin_headers,
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved"
    assert body["resolved_by"] == "test-admin@construction-ops.com"

    history = await client.get(f"/api/v1/approvals/{approval_id}/history", headers=admin_headers)
    actions = [h["action"] for h in history.json()]
    assert actions == ["requested", "approved"]

    notifications = await db_session.scalar(
        select(func.count()).select_from(Notification).where(Notification.category == "approval")
    )
    assert notifications >= 1


async def test_approval_reject_flow(client, admin_headers):
    created = await _create_approval(client, admin_headers)
    approval_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/approvals/{approval_id}/reject",
        json={"note": "Not justified"}, headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


async def test_resolve_missing_approval_404(client, admin_headers):
    response = await client.post("/api/v1/approvals/999999/approve", headers=admin_headers)
    assert response.status_code == 404


async def test_double_resolution_conflicts(client, admin_headers):
    created = await _create_approval(client, admin_headers)
    approval_id = created.json()["id"]
    await client.post(f"/api/v1/approvals/{approval_id}/approve", headers=admin_headers)
    second = await client.post(f"/api/v1/approvals/{approval_id}/reject", headers=admin_headers)
    assert second.status_code == 409


async def test_engineer_cannot_approve(client, admin_headers, db_session):
    from app.security.roles import Role
    from app.services import users as user_service

    email = "test-engineer@construction-ops.com"
    if await user_service.get_user_by_email(db_session, email) is None:
        await user_service.create_user(
            db_session, email=email, full_name="Eng", role=Role.SITE_ENGINEER.value,
            password="Passw0rd!",
        )
        await db_session.flush()
    login = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "Passw0rd!"}
    )
    eng_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = await _create_approval(client, admin_headers)
    approval_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/approvals/{approval_id}/approve", headers=eng_headers
    )
    assert response.status_code == 403


async def test_audit_endpoint_lists_ai_calls(client, admin_headers, db_session):
    db_session.add(
        AiAuditLog(workflow="unit_test_wf", provider="mock", model="mock", output_excerpt="hi")
    )
    await db_session.flush()
    response = await client.get(
        "/api/v1/audit/ai-outputs?workflow=unit_test_wf", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_audit_endpoint_forbidden_for_viewer(client, viewer_headers):
    response = await client.get("/api/v1/audit/ai-outputs", headers=viewer_headers)
    assert response.status_code == 403
