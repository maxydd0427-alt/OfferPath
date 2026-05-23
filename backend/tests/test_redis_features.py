import pytest
from fastapi import HTTPException

from app.services.job_status_cache import get_job_status, set_job_status
from app.services.rate_limiter import check_rate_limit
from app.services.redis_lock import acquire_lock, release_lock


def test_rate_limiter_increments_and_blocks() -> None:
    check_rate_limit(user_id=1, action="analysis_job", limit=2, window_seconds=60)
    check_rate_limit(user_id=1, action="analysis_job", limit=2, window_seconds=60)

    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(user_id=1, action="analysis_job", limit=2, window_seconds=60)

    assert exc_info.value.status_code == 429


def test_job_status_cache_set_get() -> None:
    set_job_status(
        job_id=42,
        status="processing",
        step="parsing_resume",
        progress=35,
        message="Extracting text.",
    )

    payload = get_job_status(42)

    assert payload is not None
    assert payload["status"] == "processing"
    assert payload["step"] == "parsing_resume"
    assert payload["progress"] == 35
    assert payload["message"] == "Extracting text."


def test_redis_lock_acquire_and_owner_safe_release() -> None:
    assert acquire_lock("lock:analysis_job:1", owner="worker:a", ttl_seconds=300)
    assert not acquire_lock("lock:analysis_job:1", owner="worker:b", ttl_seconds=300)

    release_lock("lock:analysis_job:1", owner="worker:b")
    assert not acquire_lock("lock:analysis_job:1", owner="worker:b", ttl_seconds=300)

    release_lock("lock:analysis_job:1", owner="worker:a")
    assert acquire_lock("lock:analysis_job:1", owner="worker:b", ttl_seconds=300)
