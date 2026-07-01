import json
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.db import SessionLocal, init_db
from app.models import AnalysisJob, JobStatus, Resume, User
from app.services.agent_experimental.tools import get_recent_user_analysis_context_tool
from app.services.agent_experimental.react_preview import run_react_analysis_preview
from app.services.agent_experimental.workflow import run_langchain_analysis_preview


class MockPreviewLLM:
    def invoke(self, prompt: str) -> dict:
        return {"summary_hint": "mocked LangChain preview", "prompt_seen": bool(prompt)}


def test_context_summary_from_previous_jobs(tmp_path: Path, monkeypatch) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker")
        previous_job = _create_job(db, user, resume, status=JobStatus.succeeded)
        previous_job.result_json = json.dumps(
            {
                "missing_skills": [
                    {"skill": "kubernetes", "priority": "P1", "reason": "Required"},
                    {"skill": "observability", "priority": "P2", "reason": "Required"},
                ],
                "roadmap": [
                    {"priority": "P1", "skill": "kubernetes", "task": "Deploy a service to Kubernetes"}
                ],
                "project_suggestions": ["Build an incident-ready AI service"],
            }
        )
        current_job = _create_job(db, user, resume)
        db.commit()

        context = get_recent_user_analysis_context_tool(db, current_job.id)

        assert context.source_job_ids == [previous_job.id]
        assert context.previous_missing_skills == ["kubernetes", "observability"]
        assert context.previous_roadmap_items == ["kubernetes: Deploy a service to Kubernetes"]
        assert context.previous_project_suggestions == ["Build an incident-ready AI service"]
    finally:
        db.close()


def test_langchain_preview_returns_valid_workflow_output_with_mocked_llm(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "app.services.agent_experimental.workflow.create_preview_llm",
        lambda: MockPreviewLLM(),
    )
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker testing")
        previous_job = _create_job(db, user, resume, status=JobStatus.succeeded)
        previous_job.result_json = json.dumps(
            {
                "missing_skills": [{"skill": "redis", "priority": "P1", "reason": "Required"}],
                "roadmap": [{"priority": "P1", "skill": "redis", "task": "Cache job status"}],
                "project_suggestions": ["Add Redis-backed idempotency"],
            }
        )
        current_job = _create_job(db, user, resume)
        db.commit()

        original_result_json = current_job.result_json
        output = run_langchain_analysis_preview(db, current_job.id)
        db.refresh(current_job)

        assert output.ai_provider == "langchain-experimental"
        assert output.workflow_version == "langchain-preview-v0"
        assert output.result.summary
        assert output.result.model_dump(by_alias=True)["30_day_roadmap"]
        assert output.intermediate_steps["final_result_validation"]["writes_result_json"] is False
        assert output.intermediate_steps["recent_user_analysis_context"]["previous_missing_skills"] == ["redis"]
        assert current_job.result_json == original_result_json
    finally:
        db.close()


def test_react_preview_returns_valid_workflow_output(tmp_path: Path, monkeypatch) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker testing")
        current_job = _create_job(db, user, resume)
        db.commit()

        original_result_json = current_job.result_json
        output = run_react_analysis_preview(db, current_job.id)
        db.refresh(current_job)

        assert output.ai_provider == "react-experimental"
        assert output.workflow_version == "react-preview-v0"
        assert output.result.summary
        assert output.result.model_dump(by_alias=True)["30_day_roadmap"]
        assert output.intermediate_steps["final_result_validation"]["validated_schema"] == "AnalysisResult"
        assert current_job.result_json == original_result_json
    finally:
        db.close()


def test_react_preview_records_tool_calls_and_observations(tmp_path: Path, monkeypatch) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker testing")
        current_job = _create_job(db, user, resume)
        db.commit()

        output = run_react_analysis_preview(db, current_job.id)

        tool_calls = output.intermediate_steps["tool_calls"]
        observations = output.intermediate_steps["observations"]
        assert output.intermediate_steps["available_tools"] == [
            "get_resume_text_tool",
            "get_job_description_tool",
            "get_recent_user_analysis_context_tool",
            "build_structured_result_tool",
        ]
        assert [call["action"] for call in tool_calls] == [
            "get_resume_text_tool",
            "get_job_description_tool",
            "get_recent_user_analysis_context_tool",
            "build_structured_result_tool",
        ]
        assert len(observations) == len(tool_calls)
        assert observations[-1]["observation"]["validated_schema"] == "AnalysisResult"
    finally:
        db.close()


def test_react_preview_uses_previous_successful_analysis_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker testing")
        previous_job = _create_job(db, user, resume, status=JobStatus.succeeded)
        previous_job.result_json = json.dumps(
            {
                "missing_skills": [{"skill": "kubernetes", "priority": "P1", "reason": "Required"}],
                "roadmap": [{"priority": "P1", "skill": "kubernetes", "task": "Deploy a service"}],
                "project_suggestions": ["Build a Kubernetes-backed AI service"],
            }
        )
        current_job = _create_job(db, user, resume)
        db.commit()

        output = run_react_analysis_preview(db, current_job.id)

        assert output.intermediate_steps["previous_context_used"] is True
        context_observation = next(
            observation
            for observation in output.intermediate_steps["observations"]
            if observation["tool"] == "get_recent_user_analysis_context_tool"
        )
        assert context_observation["observation"]["source_job_ids"] == [previous_job.id]
        assert "Build on prior advice: Build a Kubernetes-backed AI service" in output.result.project_suggestions
    finally:
        db.close()


def _configure_local_test_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OFFERPATH_AI_PROVIDER", "mock")
    monkeypatch.setenv("OFFERPATH_STORAGE_BACKEND", "local")
    monkeypatch.setenv("OFFERPATH_UPLOAD_DIR", str(tmp_path / "storage"))
    get_settings.cache_clear()
    init_db()


def _create_user(db, email: str | None = None) -> User:
    user = User(email=email or f"agent-{uuid4().hex}@example.com", hashed_password="not-used")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_resume(db, user: User, tmp_path: Path, text: str) -> Resume:
    resume_file = tmp_path / f"resume-{uuid4().hex}.txt"
    resume_file.write_text(text, encoding="utf-8")
    resume = Resume(
        owner_id=user.id,
        original_filename=resume_file.name,
        stored_path=str(resume_file),
        storage_backend="local",
        content_type="text/plain",
        file_size=resume_file.stat().st_size,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def _create_job(
    db,
    user: User,
    resume: Resume,
    status: JobStatus = JobStatus.failed,
) -> AnalysisJob:
    job = AnalysisJob(
        owner_id=user.id,
        resume_id=resume.id,
        target_title="AI SRE",
        job_description=(
            "We need Python, FastAPI, Redis, AWS, Kubernetes, observability, "
            "CI/CD, incident response, and reliable AI workflow operations."
        ),
        status=status,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
