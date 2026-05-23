import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.logging import get_logger, log_event
from app.db import get_db
from app.models import AnalysisJob, Resume, User
from app.schemas import JobCreate, JobDetail, JobRead
from app.services.analysis import parse_result
from app.services.idempotency import get_idempotent_job_id, set_idempotent_job_id
from app.services.job_status_cache import get_job_status, set_job_status
from app.services.queue import enqueue_analysis_job
from app.services.rate_limiter import check_rate_limit

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger(__name__)


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalysisJob:
    check_rate_limit(current_user.id, "analysis_job")

    resume = db.scalar(
        select(Resume).where(
            Resume.id == payload.resume_id,
            Resume.owner_id == current_user.id,
        )
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    if idempotency_key:
        try:
            existing_job_id = get_idempotent_job_id(current_user.id, idempotency_key)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if existing_job_id is not None:
            existing_job = db.scalar(
                select(AnalysisJob).where(
                    AnalysisJob.id == existing_job_id,
                    AnalysisJob.owner_id == current_user.id,
                )
            )
            if existing_job is not None:
                return existing_job

    job = AnalysisJob(
        owner_id=current_user.id,
        resume_id=resume.id,
        target_title=payload.target_title,
        job_description=payload.job_description,
    )
    db.add(job)
    queued_job = enqueue_analysis_job(db, job)
    if idempotency_key:
        try:
            set_idempotent_job_id(current_user.id, idempotency_key, queued_job.id)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    set_job_status(
        queued_job.id,
        status=queued_job.status.value,
        step="queued",
        progress=0,
        message="Analysis job is queued.",
    )
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
        live_status=get_job_status(job.id),
        ai_provider=job.ai_provider,
        workflow_version=job.workflow_version,
        prompt_version=job.prompt_version,
        error_message=job.error_message,
        last_error=job.last_error,
    )
