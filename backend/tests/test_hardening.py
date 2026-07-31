import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.security.rate_limit import rate_limiter
from app.security.tokens import create_access_token


async def test_security_headers_present(client):
    response = await client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def expire(self, key: str, seconds: int) -> bool:
        return True


class _Client:
    host = "203.0.113.9"


class _URL:
    path = "/api/v1/auth/login"


class _AppState:
    def __init__(self, redis: _FakeRedis) -> None:
        self.redis = redis


class _App:
    def __init__(self, redis: _FakeRedis) -> None:
        self.state = _AppState(redis)


class _FakeRequest:
    def __init__(self, redis: _FakeRedis) -> None:
        self.app = _App(redis)
        self.url = _URL()
        self.client = _Client()
        self.headers: dict[str, str] = {}
        self.cookies: dict[str, str] = {}


async def test_rate_limiter_blocks_after_limit(monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    dependency = rate_limiter(times=3, seconds=60)
    request = _FakeRequest(_FakeRedis())

    for _ in range(3):
        await dependency(request)  # within the limit

    with pytest.raises(HTTPException) as exc_info:
        await dependency(request)  # the fourth call trips the limit
    assert exc_info.value.status_code == 429


async def test_rate_limiter_disabled_under_testing(monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    dependency = rate_limiter(times=1, seconds=60)
    request = _FakeRequest(_FakeRedis())

    await dependency(request)
    await dependency(request)  # would exceed the limit, but TESTING disables enforcement


class _Client2:
    # A different client IP from the shared corporate-egress scenario this guards against.
    host = "198.51.100.4"


async def test_rate_limiter_keys_on_user_not_ip_when_authenticated(monkeypatch):
    # Two different client IPs sharing the SAME bearer token (e.g. a corporate NAT egress, or
    # simply the same person switching networks) must share one limit, not get one each — and
    # two different users behind the SAME IP must not throttle each other.
    monkeypatch.delenv("TESTING", raising=False)
    dependency = rate_limiter(times=2, seconds=60)
    redis = _FakeRedis()
    token_a = create_access_token(subject="101", role="procurement_officer")
    token_b = create_access_token(subject="202", role="procurement_officer")

    request_a1 = _FakeRequest(redis)
    request_a1.headers["authorization"] = f"Bearer {token_a}"
    request_a2 = _FakeRequest(redis)
    request_a2.headers["authorization"] = f"Bearer {token_a}"
    request_a2.client = _Client2()  # same user, different IP

    await dependency(request_a1)
    await dependency(request_a2)  # still user A, still within the shared limit of 2
    with pytest.raises(HTTPException) as exc_info:
        await dependency(request_a1)  # third call for user A trips it
    assert exc_info.value.status_code == 429

    request_b = _FakeRequest(redis)
    request_b.headers["authorization"] = f"Bearer {token_b}"
    request_b.client = request_a1.client  # same IP as user A, different user
    await dependency(request_b)  # user B has their own, unaffected budget


async def test_rate_limiter_falls_back_to_ip_without_a_token(monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    dependency = rate_limiter(times=1, seconds=60)
    request = _FakeRequest(_FakeRedis())

    await dependency(request)
    with pytest.raises(HTTPException):
        await dependency(request)


async def test_oversized_value_returns_422_not_500(client, admin_headers):
    # A project_code longer than the column (varchar(50)) is a client mistake, not a server
    # fault: it must come back as a clean 422, never a raw 500 (SQLSTATE class 22 data error).
    payload = {
        "project_code": "Z" * 60,
        "project_name": "Oversized",
        "project_type": "Tower",
        "client_name": "Client",
        "city": "Riyadh",
        "status": "Planned",
        "budget": "1000000.00",
    }
    response = await client.post("/api/v1/projects", json=payload, headers=admin_headers)
    assert response.status_code == 422


async def test_numeric_overflow_returns_422_not_500(client, admin_headers):
    payload = {
        "project_code": f"OVF-{uuid.uuid4().hex[:8]}",
        "project_name": "Overflow",
        "project_type": "Tower",
        "client_name": "Client",
        "city": "Riyadh",
        "status": "Planned",
        "budget": "1" + "0" * 20,  # far beyond numeric(16, 2)
    }
    response = await client.post("/api/v1/projects", json=payload, headers=admin_headers)
    assert response.status_code == 422


async def test_dbapi_handler_reraises_non_data_errors():
    # SQLSTATE class 22 = data exception (client) -> 422; anything else is a real server fault
    # and must propagate (500 + logged), never be masked as a client error.
    from sqlalchemy.exc import DBAPIError

    from app.main import dbapi_error_handler

    class _Orig(Exception):
        sqlstate = "22001"

    data_exc = DBAPIError.instance(
        statement="x", params=None, orig=_Orig(), dbapi_base_err=Exception
    )
    data_exc.orig.sqlstate = "22001"
    response = await dbapi_error_handler(None, data_exc)
    assert response.status_code == 422

    class _ServerOrig(Exception):
        sqlstate = "42P01"  # undefined_table — a genuine programming/server error

    server_exc = DBAPIError.instance(
        statement="x", params=None, orig=_ServerOrig(), dbapi_base_err=Exception
    )
    server_exc.orig.sqlstate = "42P01"
    with pytest.raises(DBAPIError):
        await dbapi_error_handler(None, server_exc)


def _settings(**overrides):
    # Explicit init values outrank the environment and .env in pydantic-settings, so each case
    # is exercised exactly as configured regardless of how this machine happens to be set up.
    from app.config import Settings

    defaults = {"environment": "production", "jwt_secret": "x" * 40}
    return Settings(**{**defaults, **overrides})


def test_startup_rejects_the_default_jwt_secret_outside_development():
    # The default is published in this repository, so accepting it in a deployed environment
    # would let anyone sign a valid administrator token — every role gate rests on this key.
    from app.config import DEFAULT_JWT_SECRET

    with pytest.raises(ValidationError) as excinfo:
        _settings(jwt_secret=DEFAULT_JWT_SECRET)
    assert "JWT_SECRET" in str(excinfo.value)


def test_startup_rejects_a_short_jwt_secret_outside_development():
    with pytest.raises(ValidationError):
        _settings(jwt_secret="tooshort")


def test_startup_accepts_a_real_jwt_secret_outside_development():
    assert _settings(jwt_secret="s" * 64).jwt_secret == "s" * 64


def test_development_still_runs_on_the_default_jwt_secret():
    # Local development and the test suite both use the shipped default; the guard must not
    # turn a working checkout into a startup failure.
    from app.config import DEFAULT_JWT_SECRET

    settings = _settings(environment="development", jwt_secret=DEFAULT_JWT_SECRET)
    assert settings.jwt_secret == DEFAULT_JWT_SECRET


def test_an_unrecognized_environment_is_treated_as_deployed():
    # Fail closed: only the literal "development" is exempt, so a typo or a new environment
    # name can never silently downgrade the check to permissive.
    from app.config import DEFAULT_JWT_SECRET

    with pytest.raises(ValidationError):
        _settings(environment="staging", jwt_secret=DEFAULT_JWT_SECRET)
    with pytest.raises(ValidationError):
        _settings(environment="dev", jwt_secret=DEFAULT_JWT_SECRET)
