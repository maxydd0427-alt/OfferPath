from datetime import datetime, timezone

from redis.exceptions import RedisError

from app.core.logging import get_logger, log_event
from app.services import redis_client

logger = get_logger(__name__)


def set_job_status(
    job_id: int,
    status: str,
    step: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    ttl_seconds: int = 86400,
) -> None:
    key = _build_key(job_id)
    payload = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if step is not None:
        payload["step"] = step
    if progress is not None:
        payload["progress"] = str(progress)
    if message is not None:
        payload["message"] = message

    try:
        client = redis_client.get_redis_client()
        client.hset(key, mapping=payload)
        client.expire(key, ttl_seconds)
    except RedisError as exc:
        log_event(logger, 30, "redis.job_status_cache_write_failed", job_id=job_id, error=str(exc))


def get_job_status(job_id: int) -> dict | None:
    try:
        payload = redis_client.get_redis_client().hgetall(_build_key(job_id))
    except RedisError:
        return None
    if not payload:
        return None
    if "progress" in payload:
        payload["progress"] = int(payload["progress"])
    return payload


def delete_job_status(job_id: int) -> None:
    try:
        redis_client.get_redis_client().delete(_build_key(job_id))
    except RedisError as exc:
        log_event(logger, 30, "redis.job_status_cache_delete_failed", job_id=job_id, error=str(exc))


def _build_key(job_id: int) -> str:
    return f"job:{job_id}:status"
