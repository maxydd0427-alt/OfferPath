from sqlalchemy.orm import Session

from app.models import AnalysisJob, JobStatus


def enqueue_analysis_job(db: Session, job: AnalysisJob) -> AnalysisJob:
    job.status = JobStatus.queued
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
