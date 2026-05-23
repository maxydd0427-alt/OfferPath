import json
import logging
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.models import AnalysisJob, JobStatus, utc_now
from app.services.analysis_prompts import build_gemini_prompt
from app.services.resume_parser import extract_resume_text
from app.services.storage import get_storage_service

logger = get_logger(__name__)

WORKFLOW_VERSION = "agentic-v1"
MOCK_PROMPT_VERSION = "mock-v1"
GEMINI_PROMPT_VERSION = "gemini-v1"

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


class Understanding(BaseModel):
    skills: list[str] = Field(default_factory=list)
    summary: str


class SkillGap(BaseModel):
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


class RoadmapItem(BaseModel):
    priority: str
    skill: str
    task: str


class AnalysisResult(BaseModel):
    resume_skills: list[str] = Field(default_factory=list)
    target_role_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    summary: str
    roadmap: list[RoadmapItem] = Field(default_factory=list)
    project_suggestions: list[str] = Field(default_factory=list)
    interview_questions: list[str] = Field(default_factory=list)


class AnalysisWorkflowOutput(BaseModel):
    result: AnalysisResult
    intermediate_steps: dict[str, Any]
    ai_provider: str
    workflow_version: str = WORKFLOW_VERSION
    prompt_version: str


class AnalysisProvider(ABC):
    name: str
    prompt_version: str

    @abstractmethod
    def run(self, *, target_title: str, resume_text: str, job_description: str) -> AnalysisWorkflowOutput:
        pass


class MockAnalysisProvider(AnalysisProvider):
    name = "mock"
    prompt_version = MOCK_PROMPT_VERSION

    def run(self, *, target_title: str, resume_text: str, job_description: str) -> AnalysisWorkflowOutput:
        resume_understanding = understand_resume(resume_text)
        jd_understanding = understand_job_description(job_description)
        skill_gap = compare_skill_gap(resume_understanding, jd_understanding)
        result = AnalysisResult(
            resume_skills=resume_understanding.skills,
            target_role_skills=jd_understanding.skills,
            missing_skills=skill_gap.missing_skills,
            summary=build_summary(target_title, skill_gap.missing_skills),
            roadmap=build_roadmap(skill_gap.missing_skills),
            project_suggestions=build_projects(target_title, skill_gap.missing_skills),
            interview_questions=build_questions(skill_gap.missing_skills),
        )
        return AnalysisWorkflowOutput(
            result=result,
            intermediate_steps={
                "resume_understanding": resume_understanding.model_dump(),
                "jd_understanding": jd_understanding.model_dump(),
                "skill_gap_comparison": skill_gap.model_dump(),
                "roadmap_generation": {"item_count": len(result.roadmap)},
                "project_recommendation": {"item_count": len(result.project_suggestions)},
                "interview_preparation": {"question_count": len(result.interview_questions)},
            },
            ai_provider=self.name,
            prompt_version=self.prompt_version,
        )


class GeminiAnalysisProvider(AnalysisProvider):
    name = "gemini"
    prompt_version = GEMINI_PROMPT_VERSION

    def run(self, *, target_title: str, resume_text: str, job_description: str) -> AnalysisWorkflowOutput:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError("Gemini provider requires OFFERPATH_GEMINI_API_KEY")

        raw_payload = self._generate_json(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            prompt=build_gemini_prompt(target_title, resume_text, job_description),
        )
        result = AnalysisResult.model_validate(raw_payload)
        return AnalysisWorkflowOutput(
            result=result,
            intermediate_steps={
                "provider": self.name,
                "model": settings.gemini_model,
                "validated_schema": "AnalysisResult",
                "workflow_steps": [
                    "resume_understanding",
                    "jd_understanding",
                    "skill_gap_comparison",
                    "roadmap_generation",
                    "project_recommendation",
                    "interview_preparation",
                ],
            },
            ai_provider=self.name,
            prompt_version=self.prompt_version,
        )

    def _generate_json(self, *, api_key: str, model: str, prompt: str) -> dict[str, Any]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        text = (
            response_body.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text")
        )
        if not text:
            raise RuntimeError("Gemini response did not include JSON text")
        return json.loads(text)


def extract_skills(text: str) -> list[str]:
    normalized = text.lower()
    found = {skill for skill in SKILL_KEYWORDS if re.search(rf"\b{re.escape(skill)}\b", normalized)}
    return sorted(found)


def understand_resume(resume_text: str) -> Understanding:
    skills = extract_skills(resume_text)
    summary = "Detected resume skills: " + (", ".join(skills) if skills else "none")
    return Understanding(skills=skills, summary=summary)


def understand_job_description(job_description: str) -> Understanding:
    skills = extract_skills(job_description)
    summary = "Detected target role skills: " + (", ".join(skills) if skills else "none")
    return Understanding(skills=skills, summary=summary)


def compare_skill_gap(resume: Understanding, job_description: Understanding) -> SkillGap:
    resume_skills = set(resume.skills)
    jd_skills = set(job_description.skills)
    return SkillGap(
        matched_skills=sorted(resume_skills & jd_skills),
        missing_skills=sorted(jd_skills - resume_skills),
    )


def run_analysis(db: Session, job_id: int) -> None:
    job = db.get(AnalysisJob, job_id)
    if job is None:
        log_event(logger, logging.WARNING, "analysis_job.not_found", job_id=job_id)
        return

    provider = get_analysis_provider()
    try:
        job.status = JobStatus.processing
        job.attempt_count += 1
        job.started_at = utc_now()
        job.finished_at = None
        job.last_error = None
        job.error_message = None
        job.ai_provider = provider.name
        job.workflow_version = WORKFLOW_VERSION
        job.prompt_version = provider.prompt_version
        db.commit()
        db.refresh(job)
        log_event(
            logger,
            logging.INFO,
            "analysis_job.started",
            job_id=job.id,
            attempt_count=job.attempt_count,
            ai_provider=provider.name,
            workflow_version=WORKFLOW_VERSION,
            status=job.status.value,
        )

        storage = get_storage_service()
        file_bytes = storage.read_file(job.resume.stored_path)
        resume_text = extract_resume_text(
            file_bytes=file_bytes,
            filename=job.resume.original_filename,
            content_type=job.resume.content_type,
        )
        output = provider.run(
            target_title=job.target_title,
            resume_text=resume_text,
            job_description=job.job_description,
        )

        job.result_json = json.dumps(output.result.model_dump())
        job.intermediate_json = json.dumps(output.intermediate_steps)
        job.ai_provider = output.ai_provider
        job.workflow_version = output.workflow_version
        job.prompt_version = output.prompt_version
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
            ai_provider=job.ai_provider,
            workflow_version=job.workflow_version,
            missing_skill_count=len(output.result.missing_skills),
            status=job.status.value,
        )
    except (ValidationError, json.JSONDecodeError, RuntimeError) as exc:
        _mark_job_failed(job, exc)
    except Exception as exc:  # pragma: no cover - defensive failure visibility
        _mark_job_failed(job, exc)
    finally:
        db.commit()


def run_mock_analysis(db: Session, job_id: int) -> None:
    run_analysis(db, job_id)


def parse_result(job: AnalysisJob, field: str = "result_json") -> dict | None:
    raw_value = getattr(job, field)
    if not raw_value:
        return None
    return json.loads(raw_value)


def get_analysis_provider() -> AnalysisProvider:
    settings = get_settings()
    provider_name = settings.ai_provider.lower()
    if provider_name == "gemini":
        return GeminiAnalysisProvider()
    if provider_name == "mock":
        return MockAnalysisProvider()
    raise RuntimeError(f"Unsupported AI provider: {settings.ai_provider}")

def _mark_job_failed(job: AnalysisJob, exc: Exception) -> None:
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

def build_summary(target_title: str, missing_skills: list[str]) -> str:
    if not missing_skills:
        return f"You already cover the main detected skills for {target_title}."
    return f"To become stronger for {target_title}, focus first on: {', '.join(missing_skills[:5])}."


def build_roadmap(missing_skills: list[str]) -> list[RoadmapItem]:
    if not missing_skills:
        return [
            RoadmapItem(
                priority="P1",
                skill="portfolio depth",
                task="Turn one existing project into a measurable case study.",
            )
        ]
    return [
        RoadmapItem(
            priority=f"P{index}",
            skill=skill,
            task=f"Build a small proof task using {skill}, then document decisions and trade-offs.",
        )
        for index, skill in enumerate(missing_skills[:5], start=1)
    ]


def build_projects(target_title: str, missing_skills: list[str]) -> list[str]:
    focus = ", ".join(missing_skills[:3]) if missing_skills else "production polish"
    return [
        f"Build a {target_title} portfolio project that demonstrates {focus}.",
        "Add tests, logs, deployment notes, and a short architecture decision record.",
    ]


def build_questions(missing_skills: list[str]) -> list[str]:
    skills = missing_skills[:5] or ["your strongest backend project"]
    return [f"How have you used {skill} in a real engineering trade-off?" for skill in skills]
