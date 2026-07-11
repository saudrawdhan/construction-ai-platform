"""Admin user-management: list, create, update role, activate/deactivate, and every guard
(duplicate email, invalid role, weak password, non-admin access, self-lockout, missing user)."""


async def _me_id(client, headers) -> int:
    return (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]


async def test_admin_lists_users(client, admin_headers):
    response = await client.get("/api/v1/users", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any("email" in item for item in body["items"])


async def test_admin_creates_user_who_can_log_in(client, admin_headers):
    payload = {
        "email": "new.pm@construction-ops.com",
        "full_name": "New PM",
        "role": "project_manager",
        "password": "Passw0rd!",
    }
    created = await client.post("/api/v1/users", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "project_manager"
    assert created.json()["is_active"] is True

    # the freshly created account can authenticate
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "new.pm@construction-ops.com", "password": "Passw0rd!"},
    )
    assert login.status_code == 200


async def test_create_duplicate_email_conflicts(client, admin_headers):
    payload = {
        "email": "dupe@construction-ops.com",
        "full_name": "First",
        "role": "viewer",
        "password": "Passw0rd!",
    }
    first = await client.post("/api/v1/users", headers=admin_headers, json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/users", headers=admin_headers, json=payload)
    assert second.status_code == 409


async def test_create_invalid_role_rejected(client, admin_headers):
    response = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "bad.role@construction-ops.com",
            "full_name": "Bad Role",
            "role": "wizard",
            "password": "Passw0rd!",
        },
    )
    assert response.status_code == 422


async def test_create_weak_password_rejected(client, admin_headers):
    response = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "weak@construction-ops.com",
            "full_name": "Weak",
            "role": "viewer",
            "password": "short",
        },
    )
    assert response.status_code == 422


async def test_non_admin_cannot_list_users(client, viewer_headers):
    assert (await client.get("/api/v1/users", headers=viewer_headers)).status_code == 403


async def test_non_admin_cannot_create_user(client, viewer_headers):
    response = await client.post(
        "/api/v1/users",
        headers=viewer_headers,
        json={
            "email": "blocked@construction-ops.com",
            "full_name": "Blocked",
            "role": "viewer",
            "password": "Passw0rd!",
        },
    )
    assert response.status_code == 403


async def test_deactivate_user_blocks_login(client, admin_headers):
    created = (
        await client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "email": "deactivate.me@construction-ops.com",
                "full_name": "To Deactivate",
                "role": "viewer",
                "password": "Passw0rd!",
            },
        )
    ).json()

    patched = await client.patch(
        f"/api/v1/users/{created['id']}", headers=admin_headers, json={"is_active": False}
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "deactivate.me@construction-ops.com", "password": "Passw0rd!"},
    )
    assert login.status_code == 401


async def test_update_user_role(client, admin_headers):
    created = (
        await client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "email": "promote@construction-ops.com",
                "full_name": "Promote",
                "role": "viewer",
                "password": "Passw0rd!",
            },
        )
    ).json()

    patched = await client.patch(
        f"/api/v1/users/{created['id']}", headers=admin_headers, json={"role": "executive"}
    )
    assert patched.status_code == 200
    assert patched.json()["role"] == "executive"


async def test_admin_cannot_deactivate_self(client, admin_headers):
    admin_id = await _me_id(client, admin_headers)
    response = await client.patch(
        f"/api/v1/users/{admin_id}", headers=admin_headers, json={"is_active": False}
    )
    assert response.status_code == 400


async def test_admin_cannot_demote_self(client, admin_headers):
    admin_id = await _me_id(client, admin_headers)
    response = await client.patch(
        f"/api/v1/users/{admin_id}", headers=admin_headers, json={"role": "viewer"}
    )
    assert response.status_code == 400


async def test_update_missing_user_returns_404(client, admin_headers):
    response = await client.patch(
        "/api/v1/users/999999", headers=admin_headers, json={"is_active": False}
    )
    assert response.status_code == 404
