import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, Enum, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db import Base

try:  # pgvector is used by PostgreSQL deployments; tests can run without it.
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - dependency may be absent in SQLite-only dev envs
    Vector = None  # type: ignore[assignment]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    resumes: Mapped[list["Resume"]] = relationship(back_populates="owner")
    jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="owner")
    rag_documents: Mapped[list["RAGDocument"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    original_filename: Mapped[str]
    stored_path: Mapped[str]
    storage_backend: Mapped[str] = mapped_column(default="s3")
    content_type: Mapped[str | None]
    file_size: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    owner: Mapped[User] = relationship(back_populates="resumes")
    jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="resume")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    target_title: Mapped[str]
    job_description: Mapped[str] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.queued, index=True
    )
    result_json: Mapped[str | None] = mapped_column(Text)
    intermediate_json: Mapped[str | None] = mapped_column(Text)
    ai_provider: Mapped[str] = mapped_column(default="mock")
    workflow_version: Mapped[str] = mapped_column(default="agentic-v1")
    prompt_version: Mapped[str] = mapped_column(default="mock-v1")
    error_message: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    owner: Mapped[User] = relationship(back_populates="jobs")
    resume: Mapped[Resume] = relationship(back_populates="jobs")


class RAGDocument(Base):
    __tablename__ = "rag_documents"
    __table_args__ = (
        UniqueConstraint("owner_id", "content_hash", name="uq_rag_documents_owner_content_hash"),
        CheckConstraint(
            "source_type IN ('resume', 'job_description', 'project_note', 'interview_note', 'career_knowledge')",
            name="ck_rag_documents_source_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="ck_rag_documents_status",
        ),
        Index("ix_rag_documents_owner_status", "owner_id", "status"),
        Index("ix_rag_documents_owner_source_type", "owner_id", "source_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(index=True)
    title: Mapped[str]
    storage_uri: Mapped[str | None]
    content_hash: Mapped[str] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(default="pending", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    parser_version: Mapped[str] = mapped_column(default="rag-parser-v2")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    owner: Mapped[User] = relationship(back_populates="rag_documents")
    chunks: Mapped[list["RAGChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


_embedding_column_type = Vector(get_settings().rag_embedding_dimension) if Vector is not None else JSON


class RAGChunk(Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "content_hash", name="uq_rag_chunks_document_content_hash"),
        Index("ix_rag_chunks_owner_document", "owner_id", "document_id"),
        Index("ix_rag_chunks_owner_section", "owner_id", "section_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("rag_documents.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int]
    section_type: Mapped[str] = mapped_column(default="unknown", index=True)
    heading: Mapped[str | None]
    content: Mapped[str] = mapped_column(Text)
    estimated_token_count: Mapped[int]
    content_hash: Mapped[str] = mapped_column(index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(_embedding_column_type, nullable=True)
    embedding_model: Mapped[str | None]
    search_vector: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    document: Mapped[RAGDocument] = relationship(back_populates="chunks")


class RAGRun(Base):
    __tablename__ = "rag_runs"
    __table_args__ = (
        Index("ix_rag_runs_owner_job", "owner_id", "analysis_job_id"),
        Index("ix_rag_runs_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    analysis_job_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="SET NULL"), index=True)
    query: Mapped[str] = mapped_column(Text)
    rewritten_queries: Mapped[list[str]] = mapped_column(JSON, default=list)
    retrieved_chunk_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    selected_chunk_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    latency_ms: Mapped[int] = mapped_column(default=0)
    retrieved_count: Mapped[int] = mapped_column(default=0)
    selected_count: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(default="succeeded", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    pipeline_version: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
