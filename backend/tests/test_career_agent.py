import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.db import SessionLocal, init_db
from app.models import AnalysisJob, JobStatus, Resume, User
from app.services.career_agent.planner import LLMReActPlanner, PlannerDecisionError, ReActAction
from app.services.career_agent.tools import get_recent_user_analysis_context_tool
from app.services.career_agent.career_agent import run_career_agent_preview
from app.services.rag.retrieval_models import CareerRAGContext, RetrievedContextItem


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
            "retrieve_career_rag_context_tool",
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
            "github_mcp_search_reference_projects",
            "notion_mcp_draft_learning_note",
            "gmail_mcp_draft_progress_update",
        ]
        assert output.intermediate_steps["planner"] == "heuristic_state_planner"
        assert output.intermediate_steps["planning_mode"] == "dynamic_state_based"
        assert output.intermediate_steps["stop_reason"] == "planner_finished"
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
        assert "revise_roadmap_with_user_feedback_tool" in [
            call["action"] for call in output.intermediate_steps["tool_calls"]
        ]
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


def test_career_agent_uses_rag_context_before_building_result(
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
        retriever = FakeCareerContextRetriever()

        output = run_career_agent_preview(db, current_job.id, rag_retriever=retriever)

        rag_observation = next(
            observation
            for observation in output.intermediate_steps["observations"]
            if observation["tool"] == "retrieve_career_rag_context_tool"
        )
        assert output.intermediate_steps["rag_runtime"] == "bedrock_kb"
        assert output.intermediate_steps["rag_context_used"] is True
        assert rag_observation["observation"]["metadata_filter"] == {
            "equals": {"key": "user_id", "value": str(user.id)}
        }
        assert rag_observation["observation"]["search_type"] == "HYBRID"
        assert rag_observation["observation"]["tuning"]["recommendations"]
        assert retriever.calls[0]["user_id"] == user.id
        assert "RAG context used" in output.result.summary
    finally:
        db.close()


def test_career_agent_accepts_custom_dynamic_planner(tmp_path: Path, monkeypatch) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker testing")
        current_job = _create_job(db, user, resume)
        db.commit()
        planner = FakeShortPlanner()

        output = run_career_agent_preview(db, current_job.id, planner=planner)

        assert output.intermediate_steps["planner"] == "fake_short_planner"
        assert [call["action"] for call in output.intermediate_steps["tool_calls"]] == [
            "get_resume_text_tool",
            "get_job_description_tool",
            "build_structured_result_tool",
        ]
        assert output.intermediate_steps["stop_reason"] == "planner_finished"
        assert output.result.summary
    finally:
        db.close()


def test_career_agent_can_use_llm_react_planner_with_mocked_llm(tmp_path: Path, monkeypatch) -> None:
    _configure_local_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        resume = _create_resume(db, user, tmp_path, "Python FastAPI Docker testing")
        current_job = _create_job(db, user, resume)
        db.commit()
        planner = LLMReActPlanner(
            client=FakePlannerLLMClient(
                [
                    "get_resume_text_tool",
                    "get_job_description_tool",
                    "get_recent_user_analysis_context_tool",
                    "build_structured_result_tool",
                    "github_mcp_search_reference_projects",
                    "notion_mcp_draft_learning_note",
                    "gmail_mcp_draft_progress_update",
                    "finish",
                ]
            ),
            allowed_tools=[
                "get_resume_text_tool",
                "get_job_description_tool",
                "get_recent_user_analysis_context_tool",
                "retrieve_career_rag_context_tool",
                "build_structured_result_tool",
                "revise_roadmap_with_user_feedback_tool",
                "github_mcp_search_reference_projects",
                "notion_mcp_draft_learning_note",
                "gmail_mcp_draft_progress_update",
            ],
        )

        output = run_career_agent_preview(db, current_job.id, planner=planner)

        assert output.intermediate_steps["planner"] == "llm_react_planner"
        assert output.intermediate_steps["planning_mode"] == "llm_driven"
        assert output.intermediate_steps["stop_reason"] == "planner_finished"
        assert [call["action"] for call in output.intermediate_steps["tool_calls"]] == [
            "get_resume_text_tool",
            "get_job_description_tool",
            "get_recent_user_analysis_context_tool",
            "build_structured_result_tool",
            "github_mcp_search_reference_projects",
            "notion_mcp_draft_learning_note",
            "gmail_mcp_draft_progress_update",
        ]
    finally:
        db.close()


def test_llm_react_planner_rejects_unsupported_tool() -> None:
    planner = LLMReActPlanner(
        client=FakePlannerLLMClient(["send_gmail_now"]),
        allowed_tools=["get_resume_text_tool"],
    )

    try:
        planner.choose_next_action(
            state={
                "target_title": "AI SRE",
                "resume_text": "",
                "job_description": "",
                "user_context_loaded": False,
                "rag_runtime": "disabled",
                "rag_context_loaded": False,
                "user_feedback": "",
                "feedback_used": False,
                "github_reference_projects": [],
                "notion_note_draft": None,
                "gmail_draft": None,
            },
            observations=[],
        )
    except PlannerDecisionError as exc:
        assert "unsupported tool" in str(exc)
    else:
        raise AssertionError("Expected unsupported LLM planner action to be rejected")


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


class FakeCareerContextRetriever:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def retrieve(self, *, query: str, user_id: int | str, number_of_results: int | None = None) -> CareerRAGContext:
        self.calls.append({"query": query, "user_id": user_id, "number_of_results": number_of_results})
        return CareerRAGContext(
            query=query,
            user_id=str(user_id),
            metadata_filter={"equals": {"key": "user_id", "value": str(user_id)}},
            search_type="HYBRID",
            number_of_results=5,
            latency_ms=42.0,
            items=[
                RetrievedContextItem(
                    text="Previous market JDs emphasize AWS, Kubernetes, observability, and incident response.",
                    source_uri="s3://offerpath-kb/user-notes/ai-sre.md",
                    score=0.82,
                    metadata={"user_id": str(user_id), "document_type": "market_jd"},
                )
            ],
        )


class FakeShortPlanner:
    name = "fake_short_planner"

    def choose_next_action(self, *, state: dict[str, Any], observations: list[dict[str, Any]]) -> ReActAction | None:
        if not state["resume_text"]:
            return ReActAction("Read resume first.", "get_resume_text_tool")
        if not state["job_description"]:
            return ReActAction("Read JD next.", "get_job_description_tool")
        if "result" not in state:
            return ReActAction("Build final result now.", "build_structured_result_tool")
        return None


class FakePlannerLLMClient:
    def __init__(self, actions: list[str]) -> None:
        self.actions = actions
        self.prompts: list[str] = []

    def generate_decision(self, prompt: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        action = self.actions.pop(0)
        return {
            "thought": f"Choose {action} based on current state.",
            "action": action,
        }


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
