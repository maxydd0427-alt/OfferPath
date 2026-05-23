from fastapi import HTTPException
from redis.exceptions import RedisError

from app.services import redis_client


def check_rate_limit(
    user_id: int,
    action: str,
    limit: int = 3,
    window_seconds: int = 60,
) -> None:
    key = f"rate:user:{user_id}:{action}"
    try:
        client = redis_client.get_redis_client()
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, window_seconds)
    except RedisError as exc:
        raise HTTPException(
            status_code=503,
            detail="Redis is required to create analysis jobs safely. Please try again later.",
        ) from exc

    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Too many analysis requests. Please try again later.",
        )
