from app.services import users as user_service

EMAIL = "cookie-user@construction-ops.com"
PASSWORD = "Passw0rd!"


async def _ensure_user(db_session):
    if await user_service.get_user_by_email(db_session, EMAIL) is None:
        await user_service.create_user(
            db_session, email=EMAIL, full_name="Cookie User", role="admin", password=PASSWORD
        )
        await db_session.flush()


async def test_login_sets_httponly_cookie_and_authorizes(client, db_session):
    await _ensure_user(db_session)
    login = await client.post(
        "/api/v1/auth/login", data={"username": EMAIL, "password": PASSWORD}
    )
    assert login.status_code == 200
    assert "access_token" in login.cookies
    set_cookie = login.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()

    # The cookie is now in the client jar; a protected route works with no Authorization header.
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL


async def test_logout_clears_cookie(client, db_session):
    await _ensure_user(db_session)
    await client.post("/api/v1/auth/login", data={"username": EMAIL, "password": PASSWORD})
    assert (await client.get("/api/v1/auth/me")).status_code == 200

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_request_without_credentials_is_rejected(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
