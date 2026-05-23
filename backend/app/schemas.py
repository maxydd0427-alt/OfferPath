from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models import JobStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ResumeRead(BaseModel):
    id: int
    original_filename: str
    content_type: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobCreate(BaseModel):
    resume_id: int
    target_title: str = Field(min_length=2, max_length=120)
    job_description: str = Field(min_length=40)


class JobRead(BaseModel):
    id: int
    resume_id: int
    target_title: str
    status: JobStatus
    attempt_count: int
    max_attempts: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobDetail(JobRead):
    result: dict[str, Any] | None = None
    intermediate_steps: dict[str, Any] | None = None
    ai_provider: str
    workflow_version: str
    prompt_version: str
    error_message: str | None = None
    last_error: str | None = None
