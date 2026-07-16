import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import engine, get_db
from app.main import app
from app.security.roles import Role
from app.services import users as user_service

TEST_PASSWORD = "Passw0rd!"
TEST_ACCOUNTS = {
    "admin": ("test-admin@construction-ops.com", Role.ADMIN),
    "viewer": ("test-viewer@construction-ops.com", Role.VIEWER),
    "site_engineer": ("test-site-engineer@construction-ops.com", Role.SITE_ENGINEER),
    "procurement": ("test-procurement@construction-ops.com", Role.PROCUREMENT_OFFICER),
}


@pytest_asyncio.fixture
async def db_session():
    """One connection + outer transaction per test; rolled back at teardown so tests never
    persist data. Inner app commits become savepoints via join_transaction_mode."""
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


async def _token(client: httpx.AsyncClient, db_session: AsyncSession, key: str) -> str:
    email, role = TEST_ACCOUNTS[key]
    if await user_service.get_user_by_email(db_session, email) is None:
        await user_service.create_user(
            db_session, email=email, full_name=f"Test {role.value}",
            role=role.value, password=TEST_PASSWORD,
        )
        await db_session.flush()
    response = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": TEST_PASSWORD}
    )
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def admin_headers(client, db_session):
    token = await _token(client, db_session, "admin")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def viewer_headers(client, db_session):
    token = await _token(client, db_session, "viewer")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def site_engineer_headers(client, db_session):
    token = await _token(client, db_session, "site_engineer")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def procurement_headers(client, db_session):
    token = await _token(client, db_session, "procurement")
    return {"Authorization": f"Bearer {token}"}
