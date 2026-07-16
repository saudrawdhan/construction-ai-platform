"""A small Redis-backed fixed-window rate limiter, exposed as a FastAPI dependency.

It protects the endpoints that matter most: the login route (against credential
brute-forcing), the copilot, and the agent (against runaway LLM cost). The limiter is
best-effort — if Redis is unavailable it fails open rather than locking users out, and it is
disabled under TESTING so the suite stays deterministic and offline.
"""

import os
import time
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status
from jwt import InvalidTokenError

from app.config import get_settings
from app.security.tokens import decode_access_token


def _rate_limit_identity(request: Request) -> str:
    """Prefer the authenticated user's id so a shared corporate egress IP doesn't throttle
    every employee behind it as one — a documented gap for the login endpoint that compounds
    worse on the heavier-weight agent/copilot endpoints. Falls back to client IP when no
    valid token is present, which is exactly the login endpoint's own case (no token exists
    yet by definition, so its brute-force protection is unchanged)."""
    settings = get_settings()
    raw_token = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        raw_token = auth_header[7:]
    if raw_token is None:
        raw_token = request.cookies.get(settings.auth_cookie_name)
    if raw_token:
        try:
            subject = decode_access_token(raw_token).get("sub")
        except InvalidTokenError:
            subject = None
        if subject:
            return f"user:{subject}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def rate_limiter(times: int, seconds: int) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        if os.getenv("TESTING"):
            return
        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            return

        identity = _rate_limit_identity(request)
        window = int(time.time()) // seconds
        key = f"ratelimit:{request.url.path}:{identity}:{window}"
        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, seconds)
        except Exception:
            return  # never let a Redis hiccup block legitimate traffic

        if count > times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again shortly.",
                headers={"Retry-After": str(seconds)},
            )

    return dependency
