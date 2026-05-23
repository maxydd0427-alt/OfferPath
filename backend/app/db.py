from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_database_backend, get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
database_backend = get_database_backend(settings.database_url)
connect_args = {"check_same_thread": False} if database_backend == "sqlite" else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_sqlite_dev_migrations()


def _apply_sqlite_dev_migrations() -> None:
    if database_backend != "sqlite":
        return

    inspector = inspect(engine)
    if "analysis_jobs" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("analysis_jobs")}
    migrations = {
        "last_error": "ALTER TABLE analysis_jobs ADD COLUMN last_error TEXT",
        "attempt_count": "ALTER TABLE analysis_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0",
        "max_attempts": "ALTER TABLE analysis_jobs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3",
        "started_at": "ALTER TABLE analysis_jobs ADD COLUMN started_at DATETIME",
        "finished_at": "ALTER TABLE analysis_jobs ADD COLUMN finished_at DATETIME",
        "intermediate_json": "ALTER TABLE analysis_jobs ADD COLUMN intermediate_json TEXT",
        "ai_provider": "ALTER TABLE analysis_jobs ADD COLUMN ai_provider VARCHAR NOT NULL DEFAULT 'mock'",
        "workflow_version": "ALTER TABLE analysis_jobs ADD COLUMN workflow_version VARCHAR NOT NULL DEFAULT 'agentic-v1'",
        "prompt_version": "ALTER TABLE analysis_jobs ADD COLUMN prompt_version VARCHAR NOT NULL DEFAULT 'mock-v1'",
    }

    with engine.begin() as connection:
        for column_name, statement in migrations.items():
            if column_name not in existing_columns:
                connection.execute(text(statement))
