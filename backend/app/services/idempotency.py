from redis.exceptions import RedisError

from app.services import redis_client

IDEMPOTENCY_TTL_SECONDS = 600


def get_idempotent_job_id(user_id: int, idempotency_key: str) -> int | None:
    try:
        value = redis_client.get_redis_client().get(_build_key(user_id, idempotency_key))
    except RedisError as exc:
        raise RuntimeError("Redis is required for idempotent job creation") from exc
    return int(value) if value else None


def set_idempotent_job_id(user_id: int, idempotency_key: str, job_id: int) -> None:
    try:
        redis_client.get_redis_client().set(
            _build_key(user_id, idempotency_key),
            str(job_id),
            ex=IDEMPOTENCY_TTL_SECONDS,
        )
    except RedisError as exc:
        raise RuntimeError("Redis is required for idempotent job creation") from exc


def _build_key(user_id: int, idempotency_key: str) -> str:
    return f"idempotency:user:{user_id}:jobs:{idempotency_key}"
