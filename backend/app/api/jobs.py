import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.logging import get_logger, log_event
from app.db import get_db
from app.models import AnalysisJob, Resume, User
from app.schemas import JobCreate, JobDetail, JobRead
from app.services.analysis import parse_result
from app.services.queue import enqueue_analysis_job

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger(__name__)


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalysisJob:
    resume = db.scalar(
        select(Resume).where(
            Resume.id == payload.resume_id,
            Resume.owner_id == current_user.id,
        )
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    job = AnalysisJob(
        owner_id=current_user.id,
        resume_id=resume.id,
        target_title=payload.target_title,
        job_description=payload.job_description,
    )
    db.add(job)
    queued_job = enqueue_analysis_job(db, job)
    log_event(
        logger,
        logging.INFO,
        "analysis_job.enqueued",
        job_id=queued_job.id,
        user_id=current_user.id,
        resume_id=resume.id,
        status=queued_job.status.value,
    )
    return queued_job


@router.get("", response_model=list[JobRead])
def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AnalysisJob]:
    return list(db.scalars(select(AnalysisJob).where(AnalysisJob.owner_id == current_user.id)))


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDetail:
    job = db.scalar(
        select(AnalysisJob).where(
            AnalysisJob.id == job_id,
            AnalysisJob.owner_id == current_user.id,
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobDetail(
        id=job.id,
        resume_id=job.resume_id,
        target_title=job.target_title,
        status=job.status,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        result=parse_result(job),
        intermediate_steps=parse_result(job, field="intermediate_json"),
        ai_provider=job.ai_provider,
        workflow_version=job.workflow_version,
        prompt_version=job.prompt_version,
        error_message=job.error_message,
        last_error=job.last_error,
    )
