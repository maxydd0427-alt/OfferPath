from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.redis_client import ping_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    database_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    redis_status = "ok" if ping_redis() else "unavailable"
    overall_status = "ok" if database_status == "ok" else "error"

    return {
        "status": overall_status,
        "database": database_status,
        "redis": redis_status,
    }
