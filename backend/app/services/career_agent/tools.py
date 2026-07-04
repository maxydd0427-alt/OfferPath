import json
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisJob, JobStatus
from app.services.resume_parser import extract_resume_text
from app.services.storage import get_storage_service


class RecentAnalysisContext(BaseModel):
    previous_missing_skills: list[str] = Field(default_factory=list)
    previous_roadmap_items: list[str] = Field(default_factory=list)
    previous_project_suggestions: list[str] = Field(default_factory=list)
    source_job_ids: list[int] = Field(default_factory=list)


class JobToolInput(BaseModel):
    job_id: int


def get_resume_text_tool(db: Session, job_id: int) -> str:
    job = _get_job(db, job_id)
    storage = get_storage_service()
    file_bytes = storage.read_file(job.resume.stored_path)
    return extract_resume_text(
        file_bytes=file_bytes,
        filename=job.resume.original_filename,
        content_type=job.resume.content_type,
    )


def get_job_description_tool(db: Session, job_id: int) -> str:
    return _get_job(db, job_id).job_description


def get_recent_user_analysis_context_tool(
    db: Session,
    job_id: int,
    limit: int = 3,
) -> RecentAnalysisContext:
    job = _get_job(db, job_id)
    previous_jobs = list(
        db.scalars(
            select(AnalysisJob)
            .where(
                AnalysisJob.owner_id == job.owner_id,
                AnalysisJob.id != job.id,
                AnalysisJob.status == JobStatus.succeeded,
                AnalysisJob.result_json.is_not(None),
            )
            .order_by(AnalysisJob.finished_at.desc(), AnalysisJob.id.desc())
            .limit(limit)
        )
    )

    context = RecentAnalysisContext()
    for previous_job in previous_jobs:
        try:
            result = json.loads(previous_job.result_json or "{}")
        except json.JSONDecodeError:
            continue
        context.source_job_ids.append(previous_job.id)
        context.previous_missing_skills.extend(_missing_skill_names(result.get("missing_skills", [])))
        context.previous_roadmap_items.extend(_roadmap_tasks(result.get("roadmap", [])))
        context.previous_project_suggestions.extend(_string_items(result.get("project_suggestions", [])))

    context.previous_missing_skills = _unique_preserve_order(context.previous_missing_skills)[:10]
    context.previous_roadmap_items = _unique_preserve_order(context.previous_roadmap_items)[:10]
    context.previous_project_suggestions = _unique_preserve_order(context.previous_project_suggestions)[:10]
    return context


def build_langchain_tools(db: Session) -> list[Any]:
    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        return []

    return [
        StructuredTool.from_function(
            name="get_resume_text_tool",
            description="Read parsed resume text for a known AnalysisJob id.",
            func=lambda job_id: get_resume_text_tool(db, job_id),
            args_schema=JobToolInput,
        ),
        StructuredTool.from_function(
            name="get_job_description_tool",
            description="Read the target job description for a known AnalysisJob id.",
            func=lambda job_id: get_job_description_tool(db, job_id),
            args_schema=JobToolInput,
        ),
        StructuredTool.from_function(
            name="get_recent_user_analysis_context_tool",
            description="Summarize recent successful analyses for the same AnalysisJob owner.",
            func=lambda job_id: get_recent_user_analysis_context_tool(db, job_id).model_dump(),
            args_schema=JobToolInput,
        ),
    ]


def _get_job(db: Session, job_id: int) -> AnalysisJob:
    job = db.get(AnalysisJob, job_id)
    if job is None:
        raise ValueError(f"AnalysisJob {job_id} not found")
    return job


def _missing_skill_names(items: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(items, list):
        return names
    for item in items:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("skill"), str):
            names.append(item["skill"])
    return names


def _roadmap_tasks(items: Any) -> list[str]:
    tasks: list[str] = []
    if not isinstance(items, list):
        return tasks
    for item in items:
        if isinstance(item, str):
            tasks.append(item)
        elif isinstance(item, dict):
            skill = item.get("skill")
            task = item.get("task")
            if isinstance(skill, str) and isinstance(task, str):
                tasks.append(f"{skill}: {task}")
            elif isinstance(task, str):
                tasks.append(task)
    return tasks


def _string_items(items: Any) -> list[str]:
    return [item for item in items if isinstance(item, str)] if isinstance(items, list) else []


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        normalized = item.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique
