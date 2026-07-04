import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.db import SessionLocal, init_db
from app.models import AnalysisJob, JobStatus, Resume, User
from app.services.career_agent.tools import get_recent_user_analysis_context_tool
from app.services.career_agent.career_agent import run_career_agent_preview


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


def test_career_agent_returns_valid_workflow_output(tmp_path: Path, monkeypatch) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker testing")
        current_job = _create_job(db, user, resume)
        db.commit()

        original_result_json = current_job.result_json
        output = run_career_agent_preview(db, current_job.id)
        db.refresh(current_job)

        assert output.ai_provider == "career-agent"
        assert output.workflow_version == "career-agent-react-v0"
        assert output.prompt_version == "career-agent-mcp-v0"
        assert output.result.summary
        assert output.result.model_dump(by_alias=True)["30_day_roadmap"]
        assert output.intermediate_steps["final_result_validation"]["validated_schema"] == "AnalysisResult"
        assert current_job.result_json == original_result_json
    finally:
        db.close()


def test_career_agent_records_tool_calls_and_observations(tmp_path: Path, monkeypatch) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker testing")
        current_job = _create_job(db, user, resume)
        db.commit()

        output = run_career_agent_preview(db, current_job.id)

        tool_calls = output.intermediate_steps["tool_calls"]
        observations = output.intermediate_steps["observations"]
        assert output.intermediate_steps["available_tools"] == [
            "get_resume_text_tool",
            "get_job_description_tool",
            "get_recent_user_analysis_context_tool",
            "build_structured_result_tool",
            "revise_roadmap_with_user_feedback_tool",
            "github_mcp_search_reference_projects",
            "notion_mcp_draft_learning_note",
            "gmail_mcp_draft_progress_update",
        ]
        assert [call["action"] for call in tool_calls] == [
            "get_resume_text_tool",
            "get_job_description_tool",
            "get_recent_user_analysis_context_tool",
            "build_structured_result_tool",
            "revise_roadmap_with_user_feedback_tool",
            "github_mcp_search_reference_projects",
            "notion_mcp_draft_learning_note",
            "gmail_mcp_draft_progress_update",
        ]
        assert len(observations) == len(tool_calls)
        assert observations[3]["observation"]["validated_schema"] == "AnalysisResult"
        assert observations[-1]["tool"] == "gmail_mcp_draft_progress_update"
    finally:
        db.close()


def test_career_agent_revises_roadmap_with_user_feedback(tmp_path: Path, monkeypatch) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker testing")
        current_job = _create_job(db, user, resume)
        db.commit()

        feedback = "Make the roadmap focus less on AWS and more on AI agent engineering."
        output = run_career_agent_preview(db, current_job.id, user_feedback=feedback)

        feedback_observation = next(
            observation
            for observation in output.intermediate_steps["observations"]
            if observation["tool"] == "revise_roadmap_with_user_feedback_tool"
        )
        assert output.intermediate_steps["feedback_used"] is True
        assert feedback_observation["observation"]["feedback_used"] is True
        assert feedback in output.result.summary
        assert any(feedback in suggestion for suggestion in output.result.project_suggestions)
    finally:
        db.close()


def test_career_agent_drafts_external_mcp_actions_without_publishing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker testing")
        current_job = _create_job(db, user, resume)
        db.commit()

        output = run_career_agent_preview(db, current_job.id)

        github_observation = next(
            observation
            for observation in output.intermediate_steps["observations"]
            if observation["tool"] == "github_mcp_search_reference_projects"
        )
        notion_observation = next(
            observation
            for observation in output.intermediate_steps["observations"]
            if observation["tool"] == "notion_mcp_draft_learning_note"
        )
        gmail_observation = next(
            observation
            for observation in output.intermediate_steps["observations"]
            if observation["tool"] == "gmail_mcp_draft_progress_update"
        )

        assert github_observation["observation"]["candidate_count"] >= 1
        assert notion_observation["observation"]["published"] is False
        assert gmail_observation["observation"]["sent"] is False
        assert output.intermediate_steps["external_mcp_policy"]["notion"].startswith("draft only")
        assert output.intermediate_steps["external_mcp_policy"]["gmail"].startswith("draft only")
    finally:
        db.close()


def test_career_agent_can_use_injected_real_mcp_client(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker testing")
        current_job = _create_job(db, user, resume)
        db.commit()
        mcp_client = FakeMCPToolClient()

        output = run_career_agent_preview(db, current_job.id, mcp_client=mcp_client)

        assert output.intermediate_steps["mcp_runtime"] == "real_mcp_client"
        assert [call["tool_name"] for call in mcp_client.calls] == [
            "search_repositories",
            "create_page_draft",
            "create_draft",
        ]

        github_observation = next(
            observation
            for observation in output.intermediate_steps["observations"]
            if observation["tool"] == "github_mcp_search_reference_projects"
        )
        notion_observation = next(
            observation
            for observation in output.intermediate_steps["observations"]
            if observation["tool"] == "notion_mcp_draft_learning_note"
        )
        gmail_observation = next(
            observation
            for observation in output.intermediate_steps["observations"]
            if observation["tool"] == "gmail_mcp_draft_progress_update"
        )
        assert github_observation["observation"]["candidates"][0]["name"] == "aws-samples/ai-sre-reference"
        assert notion_observation["observation"]["external_id"] == "notion-draft-1"
        assert notion_observation["observation"]["published"] is False
        assert gmail_observation["observation"]["external_id"] == "gmail-draft-1"
        assert gmail_observation["observation"]["sent"] is False
    finally:
        db.close()


def test_career_agent_uses_previous_successful_analysis_context(
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

        output = run_career_agent_preview(db, current_job.id)

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


class FakeMCPToolClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def call_tool(self, server: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append({"server": server, "tool_name": tool_name, "arguments": arguments})
        if server == "github":
            return {
                "items": [
                    {
                        "full_name": "aws-samples/ai-sre-reference",
                        "html_url": "https://github.com/aws-samples/ai-sre-reference",
                        "description": "Reference architecture for reliable AI services on AWS.",
                        "matched_skills": ["AWS", "observability", "incident response"],
                    }
                ]
            }
        if server == "notion":
            assert arguments["published"] is False
            assert arguments["safe_mode"] == "draft_only"
            return {
                "id": "notion-draft-1",
                "url": "https://notion.so/notion-draft-1",
                "title": arguments["title"],
                "sections": arguments["sections"],
                "published": False,
            }
        if server == "gmail":
            assert arguments["send"] is False
            assert arguments["safe_mode"] == "draft_only"
            return {
                "id": "gmail-draft-1",
                "subject": arguments["subject"],
                "body": arguments["body"],
                "to": arguments["to"],
                "sent": False,
            }
        raise AssertionError(f"Unexpected MCP server: {server}")


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
