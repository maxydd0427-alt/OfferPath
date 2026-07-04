from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import AnalysisJob
from app.services.career_agent.mcp_adapters import create_mcp_adapter
from app.services.career_agent.tools import (
    RecentAnalysisContext,
    get_job_description_tool,
    get_recent_user_analysis_context_tool,
    get_resume_text_tool,
)
from app.services.career_agent.result_builder import build_structured_result_tool
from app.services.analysis import AnalysisResult, AnalysisWorkflowOutput

REACT_WORKFLOW_VERSION = "career-agent-react-v0"
REACT_PROMPT_VERSION = "career-agent-mcp-v0"
REACT_MAX_STEPS = 9


@dataclass(frozen=True)
class ReActAction:
    thought: str
    tool_name: str


def run_career_agent_preview(
    db: Session,
    job_id: int,
    user_feedback: str | None = None,
) -> AnalysisWorkflowOutput:
    job = db.get(AnalysisJob, job_id)
    if job is None:
        raise ValueError(f"AnalysisJob {job_id} not found")

    state: dict[str, Any] = {
        "job_id": job_id,
        "target_title": job.target_title,
        "resume_text": "",
        "job_description": "",
        "user_context": RecentAnalysisContext(),
        "previous_context_used": False,
        "user_feedback": (user_feedback or "").strip(),
        "feedback_used": False,
        "llm_payload": {
            "summary_hint": "deterministic ReAct preview",
            **({"user_feedback": user_feedback.strip()} if user_feedback and user_feedback.strip() else {}),
        },
        "github_reference_projects": [],
        "notion_note_draft": None,
        "gmail_draft": None,
    }
    intermediate_steps: dict[str, Any] = {
        "mode": "career_agent_react_loop",
        "available_tools": _available_tools(),
        "external_mcp_policy": {
            "github": "read/search only in preview",
            "notion": "draft only; no publish without explicit user confirmation",
            "gmail": "draft only; no send without explicit user confirmation",
        },
        "tool_calls": [],
        "observations": [],
        "previous_context_used": False,
        "feedback_used": False,
        "writes_result_json": False,
    }

    for step_number, action in enumerate(_plan_actions(), start=1):
        if step_number > REACT_MAX_STEPS:
            break
        observation = _execute_action(db=db, action=action, state=state)
        intermediate_steps["tool_calls"].append(
            {
                "step": step_number,
                "reason": action.thought,
                "action": action.tool_name,
            }
        )
        intermediate_steps["observations"].append(
            {
                "step": step_number,
                "tool": action.tool_name,
                "observation": observation,
            }
        )

    result = _finalize_result(state)
    intermediate_steps["previous_context_used"] = state["previous_context_used"]
    intermediate_steps["feedback_used"] = state["feedback_used"]
    intermediate_steps["final_result_validation"] = {
        "validated_schema": "AnalysisResult",
        "writes_result_json": False,
    }

    return AnalysisWorkflowOutput(
        result=result,
        intermediate_steps=intermediate_steps,
        ai_provider="career-agent",
        workflow_version=REACT_WORKFLOW_VERSION,
        prompt_version=REACT_PROMPT_VERSION,
    )


def _available_tools() -> list[str]:
    return [
        "get_resume_text_tool",
        "get_job_description_tool",
        "get_recent_user_analysis_context_tool",
        "build_structured_result_tool",
        "revise_roadmap_with_user_feedback_tool",
        "github_mcp_search_reference_projects",
        "notion_mcp_draft_learning_note",
        "gmail_mcp_draft_progress_update",
    ]


def _plan_actions() -> list[ReActAction]:
    return [
        ReActAction(
            thought="Need resume evidence before comparing against the target role.",
            tool_name="get_resume_text_tool",
        ),
        ReActAction(
            thought="Need the target JD requirements to identify role expectations.",
            tool_name="get_job_description_tool",
        ),
        ReActAction(
            thought="Check previous successful analyses for reusable growth context.",
            tool_name="get_recent_user_analysis_context_tool",
        ),
        ReActAction(
            thought="Validate a final structured OfferPath result from gathered observations.",
            tool_name="build_structured_result_tool",
        ),
        ReActAction(
            thought="If the user provided feedback, revise the roadmap before choosing external references.",
            tool_name="revise_roadmap_with_user_feedback_tool",
        ),
        ReActAction(
            thought="Use the roadmap gaps to find GitHub reference project candidates.",
            tool_name="github_mcp_search_reference_projects",
        ),
        ReActAction(
            thought="Turn the roadmap and GitHub references into a Notion learning note draft.",
            tool_name="notion_mcp_draft_learning_note",
        ),
        ReActAction(
            thought="Prepare a Gmail progress update draft without sending it.",
            tool_name="gmail_mcp_draft_progress_update",
        ),
    ]


def _execute_action(
    *,
    db: Session,
    action: ReActAction,
    state: dict[str, Any],
) -> dict[str, Any]:
    if action.tool_name == "get_resume_text_tool":
        state["resume_text"] = get_resume_text_tool(db, state["job_id"])
        return {"resume_text_chars": len(state["resume_text"])}
    if action.tool_name == "get_job_description_tool":
        state["job_description"] = get_job_description_tool(db, state["job_id"])
        return {"job_description_chars": len(state["job_description"])}
    if action.tool_name == "get_recent_user_analysis_context_tool":
        context = get_recent_user_analysis_context_tool(db, state["job_id"])
        state["user_context"] = context
        state["previous_context_used"] = bool(
            context.previous_missing_skills
            or context.previous_roadmap_items
            or context.previous_project_suggestions
        )
        return {
            "source_job_ids": context.source_job_ids,
            "previous_missing_skill_count": len(context.previous_missing_skills),
            "previous_roadmap_item_count": len(context.previous_roadmap_items),
            "previous_project_suggestion_count": len(context.previous_project_suggestions),
        }
    if action.tool_name == "build_structured_result_tool":
        result = _finalize_result(state)
        state["result"] = result
        return {
            "validated_schema": "AnalysisResult",
            "missing_skill_count": len(result.missing_skills),
            "project_task_count": len(result.project_tasks),
        }
    if action.tool_name == "revise_roadmap_with_user_feedback_tool":
        feedback = state["user_feedback"]
        if not feedback:
            return {"feedback_used": False, "message": "No user feedback provided."}
        state["feedback_used"] = True
        state["llm_payload"]["user_feedback"] = feedback
        result = _finalize_result(state)
        state["result"] = result
        return {
            "feedback_used": True,
            "feedback": feedback,
            "validated_schema": "AnalysisResult",
            "roadmap_item_count": len(result.thirty_day_roadmap),
        }
    if action.tool_name == "github_mcp_search_reference_projects":
        adapter = create_mcp_adapter()
        result = state.get("result") or _finalize_result(state)
        state["result"] = result
        projects = adapter.search_github_reference_projects(
            target_title=state["target_title"],
            result=result,
        )
        state["github_reference_projects"] = projects
        return {
            "candidate_count": len(projects),
            "candidates": [project.model_dump() for project in projects],
        }
    if action.tool_name == "notion_mcp_draft_learning_note":
        adapter = create_mcp_adapter()
        result = state.get("result") or _finalize_result(state)
        state["result"] = result
        draft = adapter.draft_notion_learning_note(
            target_title=state["target_title"],
            result=result,
            github_projects=state["github_reference_projects"],
        )
        state["notion_note_draft"] = draft
        return draft.model_dump()
    if action.tool_name == "gmail_mcp_draft_progress_update":
        adapter = create_mcp_adapter()
        result = state.get("result") or _finalize_result(state)
        state["result"] = result
        draft = adapter.draft_gmail_progress_update(
            target_title=state["target_title"],
            result=result,
            github_projects=state["github_reference_projects"],
        )
        state["gmail_draft"] = draft
        return draft.model_dump()
    raise ValueError(f"Unsupported ReAct preview tool: {action.tool_name}")


def _finalize_result(state: dict[str, Any]) -> AnalysisResult:
    return build_structured_result_tool(
        target_title=state["target_title"],
        resume_text=state["resume_text"],
        job_description=state["job_description"],
        user_context=state["user_context"],
        llm_payload=state["llm_payload"],
    )
