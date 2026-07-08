import pytest
from fastapi import HTTPException

from app.security.rate_limit import rate_limiter


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
