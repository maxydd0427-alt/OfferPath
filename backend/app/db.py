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
    _apply_postgres_rag_v2_migrations()


def _apply_sqlite_dev_migrations() -> None:
    if database_backend != "sqlite":
        return

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    _apply_sqlite_column_migrations(
        inspector=inspector,
        table_names=table_names,
        table_name="resumes",
        migrations={
            "storage_backend": "ALTER TABLE resumes ADD COLUMN storage_backend VARCHAR NOT NULL DEFAULT 's3'",
            "file_size": "ALTER TABLE resumes ADD COLUMN file_size INTEGER NOT NULL DEFAULT 0",
        },
    )
    _apply_sqlite_column_migrations(
        inspector=inspector,
        table_names=table_names,
        table_name="analysis_jobs",
        migrations={
            "last_error": "ALTER TABLE analysis_jobs ADD COLUMN last_error TEXT",
            "attempt_count": "ALTER TABLE analysis_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0",
            "max_attempts": "ALTER TABLE analysis_jobs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3",
            "started_at": "ALTER TABLE analysis_jobs ADD COLUMN started_at DATETIME",
            "finished_at": "ALTER TABLE analysis_jobs ADD COLUMN finished_at DATETIME",
            "intermediate_json": "ALTER TABLE analysis_jobs ADD COLUMN intermediate_json TEXT",
            "ai_provider": "ALTER TABLE analysis_jobs ADD COLUMN ai_provider VARCHAR NOT NULL DEFAULT 'mock'",
            "workflow_version": "ALTER TABLE analysis_jobs ADD COLUMN workflow_version VARCHAR NOT NULL DEFAULT 'agentic-v1'",
            "prompt_version": "ALTER TABLE analysis_jobs ADD COLUMN prompt_version VARCHAR NOT NULL DEFAULT 'mock-v1'",
        },
    )


def _apply_postgres_rag_v2_migrations() -> None:
    if database_backend != "postgresql":
        return
    statements = [
        "CREATE EXTENSION IF NOT EXISTS vector",
        "ALTER TABLE rag_chunks ALTER COLUMN search_vector TYPE tsvector USING to_tsvector('simple', coalesce(content, ''))",
        "UPDATE rag_chunks SET search_vector = to_tsvector('simple', coalesce(content, '')) WHERE search_vector IS NULL",
        "CREATE INDEX IF NOT EXISTS ix_rag_chunks_search_vector ON rag_chunks USING GIN (search_vector)",
        "CREATE INDEX IF NOT EXISTS ix_rag_documents_metadata ON rag_documents USING GIN (metadata_json)",
        "CREATE INDEX IF NOT EXISTS ix_rag_chunks_metadata ON rag_chunks USING GIN (metadata_json)",
        "CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding_hnsw ON rag_chunks USING hnsw (embedding vector_cosine_ops)",
    ]
    with engine.begin() as connection:
        for statement in statements:
            try:
                connection.execute(text(statement))
            except Exception:
                # Alembic is the authoritative production migration path. This
                # dev helper must not prevent app startup on partially migrated DBs.
                continue


def _apply_sqlite_column_migrations(
    *,
    inspector,
    table_names: list[str],
    table_name: str,
    migrations: dict[str, str],
) -> None:
    if table_name not in table_names:
        return

    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    with engine.begin() as connection:
        for column_name, statement in migrations.items():
            if column_name not in existing_columns:
                connection.execute(text(statement))
