from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import AnalysisJob
from app.services.agent_experimental.tools import (
    RecentAnalysisContext,
    get_job_description_tool,
    get_recent_user_analysis_context_tool,
    get_resume_text_tool,
)
from app.services.agent_experimental.workflow import build_structured_result_tool
from app.services.analysis import AnalysisResult, AnalysisWorkflowOutput

REACT_WORKFLOW_VERSION = "react-preview-v0"
REACT_PROMPT_VERSION = "react-preview-deterministic-v0"
REACT_MAX_STEPS = 6


@dataclass(frozen=True)
class ReActAction:
    thought: str
    tool_name: str


def run_react_analysis_preview(db: Session, job_id: int) -> AnalysisWorkflowOutput:
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
        "llm_payload": {"summary_hint": "deterministic ReAct preview"},
    }
    intermediate_steps: dict[str, Any] = {
        "mode": "react_experimental_preview",
        "available_tools": _available_tools(),
        "tool_calls": [],
        "observations": [],
        "previous_context_used": False,
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
    intermediate_steps["final_result_validation"] = {
        "validated_schema": "AnalysisResult",
        "writes_result_json": False,
    }

    return AnalysisWorkflowOutput(
        result=result,
        intermediate_steps=intermediate_steps,
        ai_provider="react-experimental",
        workflow_version=REACT_WORKFLOW_VERSION,
        prompt_version=REACT_PROMPT_VERSION,
    )


def _available_tools() -> list[str]:
    return [
        "get_resume_text_tool",
        "get_job_description_tool",
        "get_recent_user_analysis_context_tool",
        "build_structured_result_tool",
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
    raise ValueError(f"Unsupported ReAct preview tool: {action.tool_name}")


def _finalize_result(state: dict[str, Any]) -> AnalysisResult:
    return build_structured_result_tool(
        target_title=state["target_title"],
        resume_text=state["resume_text"],
        job_description=state["job_description"],
        user_context=state["user_context"],
        llm_payload=state["llm_payload"],
    )
