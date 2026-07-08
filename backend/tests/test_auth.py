async def test_login_returns_token_and_user(client, admin_headers):
    response = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"
    assert body["email"] == "test-admin@construction-ops.com"


async def test_login_rejects_bad_password(client):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "test-admin@construction.local", "password": "wrong"},
    )
    assert response.status_code == 401


async def test_protected_route_requires_token(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
