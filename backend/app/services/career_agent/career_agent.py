from typing import Any

from sqlalchemy.orm import Session

from app.models import AnalysisJob
from app.services.career_agent.mcp_adapters import MCPAdapterConfig, MCPToolClient, create_mcp_adapter
from app.services.career_agent.planner import AgentPlanner, ReActAction, create_agent_planner
from app.services.career_agent.tools import (
    RecentAnalysisContext,
    get_job_description_tool,
    get_recent_user_analysis_context_tool,
    get_resume_text_tool,
)
from app.services.career_agent.structured_result_builder import build_structured_result_tool
from app.services.analysis import AnalysisResult, AnalysisWorkflowOutput
from app.services.rag import CareerContextRetriever, build_rag_tuning_report, retrieve_career_context_tool

REACT_WORKFLOW_VERSION = "career-agent-react-v0"
REACT_PROMPT_VERSION = "career-agent-mcp-v0"
REACT_MAX_STEPS = 12


def run_career_agent_preview(
    db: Session,
    job_id: int,
    user_feedback: str | None = None,
    mcp_client: MCPToolClient | None = None,
    mcp_config: MCPAdapterConfig | None = None,
    rag_retriever: CareerContextRetriever | None = None,
    planner: AgentPlanner | None = None,
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
        "user_context_loaded": False,
        "rag_context": None,
        "rag_context_loaded": False,
        "previous_context_used": False,
        "rag_context_used": False,
        "user_feedback": (user_feedback or "").strip(),
        "feedback_used": False,
        "llm_payload": {
            "summary_hint": "deterministic ReAct preview",
            **({"user_feedback": user_feedback.strip()} if user_feedback and user_feedback.strip() else {}),
        },
        "github_reference_projects": [],
        "notion_note_draft": None,
        "gmail_draft": None,
        "mcp_adapter": create_mcp_adapter(client=mcp_client, config=mcp_config),
        "mcp_runtime": "real_mcp_client" if mcp_client is not None else "deterministic_fallback",
        "rag_retriever": rag_retriever,
        "rag_runtime": "bedrock_kb" if rag_retriever is not None else "disabled",
    }
    active_planner = planner or create_agent_planner(allowed_tools=_available_tools())
    intermediate_steps: dict[str, Any] = {
        "mode": "career_agent_react_loop",
        "planner": active_planner.name,
        "planning_mode": "llm_driven" if active_planner.name == "llm_react_planner" else "dynamic_state_based",
        "max_steps": REACT_MAX_STEPS,
        "mcp_runtime": state["mcp_runtime"],
        "rag_runtime": state["rag_runtime"],
        "available_tools": _available_tools(),
        "rag_policy": {
            "metadata_filter": "always filter by user_id",
            "search_type": "HYBRID by default",
            "metrics": "CloudWatch latency/item/error metrics when enabled",
        },
        "external_mcp_policy": {
            "github": "read/search only in preview",
            "notion": "draft only; no publish without explicit user confirmation",
            "gmail": "draft only; no send without explicit user confirmation",
        },
        "tool_calls": [],
        "observations": [],
        "previous_context_used": False,
        "rag_context_used": False,
        "feedback_used": False,
        "writes_result_json": False,
    }

    for step_number in range(1, REACT_MAX_STEPS + 1):
        action = active_planner.choose_next_action(
            state=state,
            observations=intermediate_steps["observations"],
        )
        if action is None:
            intermediate_steps["stop_reason"] = "planner_finished"
            break
        if action.tool_name not in _available_tools():
            raise ValueError(f"Planner selected unsupported tool: {action.tool_name}")
        observation = _execute_action(db=db, action=action, state=state)
        intermediate_steps["tool_calls"].append(
            {
                "step": step_number,
                "planner": active_planner.name,
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
    else:
        intermediate_steps["stop_reason"] = "max_steps_reached"

    result = _finalize_result(state)
    intermediate_steps["previous_context_used"] = state["previous_context_used"]
    intermediate_steps["rag_context_used"] = state["rag_context_used"]
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
        "retrieve_career_rag_context_tool",
        "build_structured_result_tool",
        "revise_roadmap_with_user_feedback_tool",
        "github_mcp_search_reference_projects",
        "notion_mcp_draft_learning_note",
        "gmail_mcp_draft_progress_update",
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
        state["user_context_loaded"] = True
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
    if action.tool_name == "retrieve_career_rag_context_tool":
        rag_context = retrieve_career_context_tool(
            db,
            state["job_id"],
            state["rag_retriever"],
        )
        state["rag_context"] = rag_context
        state["rag_context_loaded"] = True
        state["rag_context_used"] = rag_context.used
        state["llm_payload"]["rag_context_items"] = [item.model_dump() for item in rag_context.items[:5]]
        tuning_report = build_rag_tuning_report(rag_context)
        state["rag_tuning_report"] = tuning_report
        return {
            "enabled": rag_context.enabled,
            "used": rag_context.used,
            "item_count": len(rag_context.items),
            "search_type": rag_context.search_type,
            "metadata_filter": rag_context.metadata_filter,
            "latency_ms": rag_context.latency_ms,
            "error": rag_context.error,
            "tuning": tuning_report.model_dump(),
            "sources": [item.source_uri for item in rag_context.items if item.source_uri],
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
        adapter = state["mcp_adapter"]
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
        adapter = state["mcp_adapter"]
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
        adapter = state["mcp_adapter"]
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
