import json
import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import AnalysisJob, JobStatus, utc_now

logger = get_logger(__name__)

SKILL_KEYWORDS = {
    "python",
    "fastapi",
    "django",
    "sql",
    "postgresql",
    "redis",
    "aws",
    "docker",
    "kubernetes",
    "ci/cd",
    "testing",
    "rest",
    "async",
    "sqs",
    "s3",
    "linux",
    "javascript",
    "typescript",
}


def extract_skills(text: str) -> list[str]:
    normalized = text.lower()
    found = {skill for skill in SKILL_KEYWORDS if re.search(rf"\b{re.escape(skill)}\b", normalized)}
    return sorted(found)


def run_mock_analysis(db: Session, job_id: int) -> None:
    job = db.get(AnalysisJob, job_id)
    if job is None:
        log_event(logger, logging.WARNING, "analysis_job.not_found", job_id=job_id)
        return

    try:
        job.status = JobStatus.processing
        job.attempt_count += 1
        job.started_at = utc_now()
        job.finished_at = None
        job.last_error = None
        job.error_message = None
        db.commit()
        db.refresh(job)
        log_event(
            logger,
            logging.INFO,
            "analysis_job.started",
            job_id=job.id,
            attempt_count=job.attempt_count,
            status=job.status.value,
        )

        resume_text = _read_resume_text(job.resume.stored_path)
        resume_skills = extract_skills(resume_text)
        jd_skills = extract_skills(job.job_description)
        missing_skills = sorted(set(jd_skills) - set(resume_skills))

        result = {
            "resume_skills": resume_skills,
            "target_role_skills": jd_skills,
            "missing_skills": missing_skills,
            "summary": _build_summary(job.target_title, missing_skills),
            "roadmap": _build_roadmap(missing_skills),
            "project_suggestions": _build_projects(job.target_title, missing_skills),
            "interview_questions": _build_questions(missing_skills),
        }

        job.result_json = json.dumps(result)
        job.status = JobStatus.succeeded
        job.error_message = None
        job.last_error = None
        job.finished_at = utc_now()
        log_event(
            logger,
            logging.INFO,
            "analysis_job.succeeded",
            job_id=job.id,
            attempt_count=job.attempt_count,
            missing_skill_count=len(missing_skills),
            status=job.status.value,
        )
    except Exception as exc:  # pragma: no cover - defensive failure visibility
        error = str(exc)
        job.status = JobStatus.failed
        job.error_message = error
        job.last_error = error
        job.finished_at = utc_now()
        log_event(
            logger,
            logging.ERROR,
            "analysis_job.failed",
            job_id=job.id,
            attempt_count=job.attempt_count,
            error=error,
            status=job.status.value,
        )
    finally:
        db.commit()


def parse_result(job: AnalysisJob) -> dict | None:
    if not job.result_json:
        return None
    return json.loads(job.result_json)


def _read_resume_text(path: str) -> str:
    resume_path = Path(path)
    if resume_path.suffix.lower() not in {".txt", ".md", ".csv"}:
        return resume_path.name
    return resume_path.read_text(encoding="utf-8", errors="ignore")


def _build_summary(target_title: str, missing_skills: list[str]) -> str:
    if not missing_skills:
        return f"You already cover the main detected skills for {target_title}."
    return f"To become stronger for {target_title}, focus first on: {', '.join(missing_skills[:5])}."


def _build_roadmap(missing_skills: list[str]) -> list[dict[str, str]]:
    if not missing_skills:
        return [{"priority": "P1", "skill": "portfolio depth", "task": "Turn one existing project into a measurable case study."}]
    return [
        {
            "priority": f"P{index}",
            "skill": skill,
            "task": f"Build a small proof task using {skill}, then document decisions and trade-offs.",
        }
        for index, skill in enumerate(missing_skills[:5], start=1)
    ]


def _build_projects(target_title: str, missing_skills: list[str]) -> list[str]:
    focus = ", ".join(missing_skills[:3]) if missing_skills else "production polish"
    return [
        f"Build a {target_title} portfolio project that demonstrates {focus}.",
        "Add tests, logs, deployment notes, and a short architecture decision record.",
    ]


def _build_questions(missing_skills: list[str]) -> list[str]:
    skills = missing_skills[:5] or ["your strongest backend project"]
    return [f"How have you used {skill} in a real engineering trade-off?" for skill in skills]
