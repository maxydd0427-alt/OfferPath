from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings


def get_redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


def ping_redis() -> bool:
    try:
        return bool(get_redis_client().ping())
    except RedisError:
        return False


def acquire_lock(key: str, ttl_seconds: int) -> bool:
    try:
        return bool(get_redis_client().set(key, "1", nx=True, ex=ttl_seconds))
    except RedisError:
        return False


def release_lock(key: str) -> None:
    try:
        get_redis_client().delete(key)
    except RedisError:
        return
