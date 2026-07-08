from redis.asyncio import Redis

from app.config import get_settings

settings = get_settings()


def create_redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)
