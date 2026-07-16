import pytest
from fastapi import HTTPException

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
