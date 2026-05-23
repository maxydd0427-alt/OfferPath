import enum
from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


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


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    original_filename: Mapped[str]
    stored_path: Mapped[str]
    content_type: Mapped[str | None]
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
