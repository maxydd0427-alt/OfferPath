from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, health, jobs, resumes
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, log_event
from app.db import init_db

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log_event(logger, 20, "api.startup", app_name=settings.app_name)
    init_db()
    yield
    log_event(logger, 20, "api.shutdown", app_name=settings.app_name)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(resumes.router)
app.include_router(jobs.router)
