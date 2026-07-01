import json
import logging
import os
import re
import socket
import ssl
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.models import AnalysisJob, JobStatus, utc_now
from app.services.analysis_prompts import build_gemini_step_prompt, build_gemini_validation_prompt
from app.services.job_status_cache import set_job_status
from app.services.redis_lock import acquire_lock, release_lock
from app.services.resume_parser import extract_resume_text
from app.services.storage import get_storage_service

logger = get_logger(__name__)

WORKFLOW_VERSION = "agentic-v1"
MOCK_PROMPT_VERSION = "mock-v1"
GEMINI_PROMPT_VERSION = "gemini-v1"
GEMINI_JSON_RETRIES = 2

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
    missing_skills: list["PrioritizedSkill"] = Field(default_factory=list)
    weak_skills: list[str] = Field(default_factory=list)
    partially_matched_skills: list[str] = Field(default_factory=list)


class RoadmapItem(BaseModel):
    priority: str
    skill: str
    task: str


class TimedRoadmapItem(RoadmapItem):
    days: str


class PrioritizedSkill(BaseModel):
    skill: str
    priority: str = Field(pattern=r"^P[1-3]$")
    reason: str


class ProjectTask(BaseModel):
    title: str
    description: str
    skills: list[str] = Field(default_factory=list)
    success_metric: str


class AnalysisResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    resume_skills: list[str] = Field(default_factory=list)
    target_role_skills: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    weak_skills: list[str] = Field(default_factory=list)
    partially_matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[PrioritizedSkill] = Field(default_factory=list)
    evidence_from_resume: list[str] = Field(default_factory=list)
    evidence_from_jd: list[str] = Field(default_factory=list)
    summary: str
    thirty_day_roadmap: list[TimedRoadmapItem] = Field(
        default_factory=list,
        validation_alias=AliasChoices("30_day_roadmap", "thirty_day_roadmap"),
        serialization_alias="30_day_roadmap",
    )
    roadmap: list[RoadmapItem] = Field(default_factory=list)
    project_tasks: list[ProjectTask] = Field(default_factory=list)
    project_suggestions: list[str] = Field(default_factory=list)
    interview_questions: list[str] = Field(default_factory=list)
    interview_talking_points: list[str] = Field(default_factory=list)
    resume_improvement_suggestions: list[str] = Field(default_factory=list)


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


class MissingAPIKeyError(RuntimeError):
    pass


class LLMRequestError(RuntimeError):
    pass


class InvalidAIJSONError(RuntimeError):
    pass


class AISchemaValidationError(RuntimeError):
    pass


class ResumeExtractionError(RuntimeError):
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
            matched_skills=skill_gap.matched_skills,
            weak_skills=skill_gap.weak_skills,
            partially_matched_skills=skill_gap.partially_matched_skills,
            missing_skills=skill_gap.missing_skills,
            evidence_from_resume=build_resume_evidence(resume_text, resume_understanding.skills),
            evidence_from_jd=build_jd_evidence(job_description, jd_understanding.skills),
            summary=build_summary(target_title, skill_gap.missing_skills),
            thirty_day_roadmap=build_30_day_roadmap(skill_gap.missing_skills),
            roadmap=build_roadmap(skill_gap.missing_skills),
            project_tasks=build_project_tasks(target_title, skill_gap.missing_skills),
            project_suggestions=build_projects(target_title, skill_gap.missing_skills),
            interview_questions=build_questions(skill_gap.missing_skills),
            interview_talking_points=build_talking_points(target_title, skill_gap),
            resume_improvement_suggestions=build_resume_suggestions(skill_gap.missing_skills),
        )
        return AnalysisWorkflowOutput(
            result=result,
            intermediate_steps={
                "resume_understanding": resume_understanding.model_dump(),
                "jd_understanding": jd_understanding.model_dump(),
                "skill_gap_comparison": skill_gap.model_dump(),
                "roadmap_generation": {"item_count": len(result.roadmap)},
                "project_recommendation": {"item_count": len(result.project_tasks)},
                "interview_preparation": {"question_count": len(result.interview_questions)},
                "final_result_validation": {"validated_schema": "AnalysisResult"},
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
            raise MissingAPIKeyError("missing API key: set OFFERPATH_GEMINI_API_KEY to use Gemini")

        context: dict[str, Any] = {}
        for step in [
            "resume_understanding",
            "jd_understanding",
            "skill_gap_comparison",
            "roadmap_generation",
            "project_recommendation",
            "interview_preparation",
        ]:
            context[step] = self._generate_json_with_retry(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                prompt=build_gemini_step_prompt(
                    step=step,
                    target_title=target_title,
                    resume_text=resume_text,
                    job_description=job_description,
                    context=context,
                ),
                step=step,
            )

        result, raw_payload = self._generate_valid_result_with_retry(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            prompt=build_gemini_validation_prompt(
                target_title=target_title,
                resume_text=resume_text,
                job_description=job_description,
                context=context,
            ),
        )
        context["final_result_validation"] = {
            "validated_schema": "AnalysisResult",
            "missing_skill_count": len(result.missing_skills),
            "project_task_count": len(result.project_tasks),
            "raw_keys": sorted(raw_payload.keys()),
        }
        return AnalysisWorkflowOutput(
            result=result,
            intermediate_steps={
                "provider": self.name,
                "model": settings.gemini_model,
                **context,
            },
            ai_provider=self.name,
            prompt_version=self.prompt_version,
        )

    def _generate_json_with_retry(self, *, api_key: str, model: str, prompt: str, step: str) -> dict[str, Any]:
        last_error: Exception | None = None
        retry_prompt = prompt
        for attempt in range(1, GEMINI_JSON_RETRIES + 2):
            try:
                return self._generate_json(api_key=api_key, model=model, prompt=retry_prompt)
            except json.JSONDecodeError as exc:
                last_error = exc
                retry_prompt = (
                    f"{prompt}\n\nYour previous response was invalid JSON for step {step}. "
                    "Return only parseable JSON with double-quoted property names."
                )
            except InvalidAIJSONError as exc:
                last_error = exc
                retry_prompt = (
                    f"{prompt}\n\nYour previous response did not include valid JSON for step {step}. "
                    "Return only the JSON object requested by the schema."
                )
            except LLMRequestError:
                raise
        raise InvalidAIJSONError(f"invalid JSON from Gemini step {step}: {last_error}") from last_error

    def _generate_valid_result_with_retry(
        self,
        *,
        api_key: str,
        model: str,
        prompt: str,
    ) -> tuple[AnalysisResult, dict[str, Any]]:
        last_error: Exception | None = None
        retry_prompt = prompt
        for attempt in range(1, GEMINI_JSON_RETRIES + 2):
            raw_payload = self._generate_json_with_retry(
                api_key=api_key,
                model=model,
                prompt=retry_prompt,
                step="final_result_validation",
            )
            try:
                return AnalysisResult.model_validate(raw_payload), raw_payload
            except ValidationError as exc:
                last_error = exc
                retry_prompt = (
                    f"{prompt}\n\nYour previous JSON failed schema validation: {exc}. "
                    "Return the complete final object with all required fields and correct types."
                )
        raise AISchemaValidationError(f"schema validation failure in final_result_validation: {last_error}") from last_error

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
            with urllib.request.urlopen(request, timeout=30, context=build_ssl_context()) as response:
                response_body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMRequestError(
                f"LLM request failure: Gemini request failed with HTTP {exc.code}: {body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMRequestError(f"LLM request failure: Gemini request failed: {exc}") from exc

        text = (
            response_body.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text")
        )
        if not text:
            raise InvalidAIJSONError("invalid JSON: Gemini response did not include JSON text")
        return json.loads(text)


def build_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:  # pragma: no cover - standard library fallback
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


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
    missing = sorted(jd_skills - resume_skills)
    return SkillGap(
        matched_skills=sorted(resume_skills & jd_skills),
        missing_skills=[
            PrioritizedSkill(
                skill=skill,
                priority="P1" if index < 2 else "P2" if index < 5 else "P3",
                reason=f"{skill} appears in the target role but is not strongly evidenced in the resume.",
            )
            for index, skill in enumerate(missing)
        ],
        weak_skills=[],
        partially_matched_skills=[],
    )


def run_analysis(db: Session, job_id: int) -> bool:
    lock_key = f"lock:analysis_job:{job_id}"
    lock_owner = f"worker:{socket.gethostname()}:{os.getpid()}"
    if not acquire_lock(lock_key, owner=lock_owner, ttl_seconds=300):
        log_event(logger, logging.WARNING, "analysis_job.lock_not_acquired", job_id=job_id)
        return False

    job: AnalysisJob | None = None
    try:
        job = db.get(AnalysisJob, job_id)
        if job is None:
            log_event(logger, logging.WARNING, "analysis_job.not_found", job_id=job_id)
            return False
        if job.status == JobStatus.succeeded:
            log_event(logger, logging.INFO, "analysis_job.already_succeeded", job_id=job_id)
            return False

        provider = get_analysis_provider()
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
        set_job_status(
            job.id,
            status=job.status.value,
            step="started",
            progress=5,
            message="Analysis worker started.",
        )
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

        set_job_status(
            job.id,
            status=job.status.value,
            step="reading_resume_from_s3",
            progress=20,
            message="Reading resume bytes from storage.",
        )
        storage = get_storage_service()
        file_bytes = storage.read_file(job.resume.stored_path)
        set_job_status(
            job.id,
            status=job.status.value,
            step="parsing_resume",
            progress=35,
            message="Extracting resume text.",
        )
        try:
            resume_text = extract_resume_text(
                file_bytes=file_bytes,
                filename=job.resume.original_filename,
                content_type=job.resume.content_type,
            )
        except (RuntimeError, ValueError) as exc:
            raise ResumeExtractionError(f"PDF text extraction failure: {exc}") from exc
        set_job_status(
            job.id,
            status=job.status.value,
            step="running_analysis_provider",
            progress=60,
            message=f"Running {provider.name} analysis provider.",
        )
        output = provider.run(
            target_title=job.target_title,
            resume_text=resume_text,
            job_description=job.job_description,
        )

        set_job_status(
            job.id,
            status=job.status.value,
            step="saving_result",
            progress=90,
            message="Saving analysis result.",
        )
        job.result_json = json.dumps(output.result.model_dump(by_alias=True))
        job.intermediate_json = json.dumps(output.intermediate_steps)
        job.ai_provider = output.ai_provider
        job.workflow_version = output.workflow_version
        job.prompt_version = output.prompt_version
        job.status = JobStatus.succeeded
        job.error_message = None
        job.last_error = None
        job.finished_at = utc_now()
        set_job_status(
            job.id,
            status=job.status.value,
            step="completed",
            progress=100,
            message="Analysis completed.",
        )
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
        return True
    except (ValidationError, json.JSONDecodeError, RuntimeError) as exc:
        if job is not None:
            _mark_job_failed(job, exc)
        else:
            log_event(logger, logging.ERROR, "analysis_job.failed_before_load", job_id=job_id, error=str(exc))
    except Exception as exc:  # pragma: no cover - defensive failure visibility
        if job is not None:
            _mark_job_failed(job, exc)
        else:
            log_event(logger, logging.ERROR, "analysis_job.failed_before_load", job_id=job_id, error=str(exc))
    finally:
        db.commit()
        release_lock(lock_key, owner=lock_owner)
    return False


def run_mock_analysis(db: Session, job_id: int) -> bool:
    return run_analysis(db, job_id)


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
    error = classify_analysis_error(exc)
    job.status = JobStatus.failed
    job.error_message = error
    job.last_error = error
    job.finished_at = utc_now()
    set_job_status(
        job.id,
        status=job.status.value,
        step="failed",
        progress=None,
        message=error,
    )
    log_event(
        logger,
        logging.ERROR,
        "analysis_job.failed",
        job_id=job.id,
        attempt_count=job.attempt_count,
        error=error,
        status=job.status.value,
    )


def classify_analysis_error(exc: Exception) -> str:
    if isinstance(exc, ResumeExtractionError):
        return f"PDF text extraction: {exc}"
    if isinstance(exc, MissingAPIKeyError):
        return str(exc)
    if isinstance(exc, LLMRequestError):
        return str(exc)
    if isinstance(exc, InvalidAIJSONError) or isinstance(exc, json.JSONDecodeError):
        return f"invalid JSON: {exc}"
    if isinstance(exc, AISchemaValidationError) or isinstance(exc, ValidationError):
        return f"schema validation failure: {exc}"
    return str(exc)


def build_summary(target_title: str, missing_skills: list[PrioritizedSkill]) -> str:
    if not missing_skills:
        return f"You already cover the main detected skills for {target_title}."
    skill_names = [item.skill for item in missing_skills[:5]]
    return f"To become stronger for {target_title}, focus first on: {', '.join(skill_names)}."


def build_roadmap(missing_skills: list[PrioritizedSkill]) -> list[RoadmapItem]:
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
            priority=skill.priority,
            skill=skill.skill,
            task=f"Build a small proof task using {skill.skill}, then document decisions and trade-offs.",
        )
        for skill in missing_skills[:5]
    ]


def build_30_day_roadmap(missing_skills: list[PrioritizedSkill]) -> list[TimedRoadmapItem]:
    roadmap = build_roadmap(missing_skills)
    day_ranges = ["Day 1-7", "Day 8-14", "Day 15-21", "Day 22-30", "Day 22-30"]
    return [
        TimedRoadmapItem(
            priority=item.priority,
            skill=item.skill,
            task=item.task,
            days=day_ranges[index],
        )
        for index, item in enumerate(roadmap[:5])
    ]


def build_project_tasks(target_title: str, missing_skills: list[PrioritizedSkill]) -> list[ProjectTask]:
    skills = [item.skill for item in missing_skills[:3]] or ["observability", "testing", "deployment"]
    return [
        ProjectTask(
            title=f"{target_title} readiness project",
            description="Build a small production-style service with async processing, logs, tests, and deployment notes.",
            skills=skills,
            success_metric="Demo the service, show a passing test suite, and explain one reliability trade-off.",
        )
    ]


def build_projects(target_title: str, missing_skills: list[PrioritizedSkill]) -> list[str]:
    focus = ", ".join(item.skill for item in missing_skills[:3]) if missing_skills else "production polish"
    return [
        f"Build a {target_title} portfolio project that demonstrates {focus}.",
        "Add tests, logs, deployment notes, and a short architecture decision record.",
    ]


def build_questions(missing_skills: list[PrioritizedSkill]) -> list[str]:
    skills = [item.skill for item in missing_skills[:5]] or ["your strongest backend project"]
    return [f"How have you used {skill} in a real engineering trade-off?" for skill in skills]


def build_talking_points(target_title: str, skill_gap: SkillGap) -> list[str]:
    matched = ", ".join(skill_gap.matched_skills[:3]) or "your strongest existing engineering skills"
    missing = ", ".join(item.skill for item in skill_gap.missing_skills[:3]) or "deeper production impact"
    return [
        f"For {target_title}, explain how {matched} already maps to the role.",
        f"Prepare a growth story showing how you are closing gaps in {missing}.",
    ]


def build_resume_suggestions(missing_skills: list[PrioritizedSkill]) -> list[str]:
    if not missing_skills:
        return ["Add metrics, architecture context, and operational impact to your strongest project bullets."]
    return [
        f"Add a project bullet that proves {item.skill}: include tool choice, scale, failure mode, and measurable result."
        for item in missing_skills[:3]
    ]


def build_resume_evidence(resume_text: str, skills: list[str]) -> list[str]:
    if not skills:
        return ["No strong skill keywords were detected in the resume text."]
    return [f"Resume mentions {skill}." for skill in skills[:6]]


def build_jd_evidence(job_description: str, skills: list[str]) -> list[str]:
    if not skills:
        return ["No supported skill keywords were detected in the job description."]
    return [f"JD asks for {skill}." for skill in skills[:6]]
