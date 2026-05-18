from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import SessionLocal, get_db
from app.models import AnalysisJob, Resume, User
from app.schemas import JobCreate, JobDetail, JobRead
from app.services.analysis import parse_result, run_mock_analysis

router = APIRouter(prefix="/jobs", tags=["jobs"])


def process_job_in_background(job_id: int) -> None:
    db = SessionLocal()
    try:
        run_mock_analysis(db, job_id)
    finally:
        db.close()


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
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
    db.commit()
    db.refresh(job)

    background_tasks.add_task(process_job_in_background, job.id)
    return job


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
        created_at=job.created_at,
        updated_at=job.updated_at,
        result=parse_result(job),
        error_message=job.error_message,
    )
