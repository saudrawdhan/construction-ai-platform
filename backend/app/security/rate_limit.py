"""A small Redis-backed fixed-window rate limiter, exposed as a FastAPI dependency.

It protects the two endpoints that matter most: the login route (against credential
brute-forcing) and the copilot (against runaway LLM cost). The limiter is best-effort — if
Redis is unavailable it fails open rather than locking users out, and it is disabled under
TESTING so the suite stays deterministic and offline.
"""

import os
import time
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status


def rate_limiter(times: int, seconds: int) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        if os.getenv("TESTING"):
            return
        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            return

        client = request.client.host if request.client else "unknown"
        window = int(time.time()) // seconds
        key = f"ratelimit:{request.url.path}:{client}:{window}"
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
