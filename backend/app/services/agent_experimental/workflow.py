import json
from typing import Any, Protocol, TypedDict

from sqlalchemy.orm import Session

from app.models import AnalysisJob
from app.services.agent_experimental.tools import (
    RecentAnalysisContext,
    get_job_description_tool,
    get_recent_user_analysis_context_tool,
    get_resume_text_tool,
)
from app.services.analysis import (
    AnalysisResult,
    AnalysisWorkflowOutput,
    MockAnalysisProvider,
    build_project_tasks,
    build_resume_suggestions,
)

EXPERIMENTAL_WORKFLOW_VERSION = "langchain-preview-v0"
EXPERIMENTAL_PROMPT_VERSION = "langchain-preview-mockable-v0"


class PreviewLLM(Protocol):
    def invoke(self, prompt: str) -> str | dict[str, Any]:
        pass


class PreviewState(TypedDict, total=False):
    job_id: int
    target_title: str
    resume_text: str
    job_description: str
    user_context: dict[str, Any]
    llm_payload: dict[str, Any]
    result: AnalysisResult
    intermediate_steps: dict[str, Any]


class DeterministicPreviewLLM:
    def invoke(self, prompt: str) -> dict[str, Any]:
        return {"summary_hint": "deterministic experimental preview", "prompt_length": len(prompt)}


def run_langchain_analysis_preview(db: Session, job_id: int) -> AnalysisWorkflowOutput:
    job = db.get(AnalysisJob, job_id)
    if job is None:
        raise ValueError(f"AnalysisJob {job_id} not found")

    state: PreviewState = {
        "job_id": job_id,
        "target_title": job.target_title,
        "intermediate_steps": {
            "mode": "experimental_preview",
            "writes_result_json": False,
        },
    }
    final_state = _run_graph_or_fallback(db=db, state=state, llm=create_preview_llm())
    return AnalysisWorkflowOutput(
        result=final_state["result"],
        intermediate_steps=final_state["intermediate_steps"],
        ai_provider="langchain-experimental",
        workflow_version=EXPERIMENTAL_WORKFLOW_VERSION,
        prompt_version=EXPERIMENTAL_PROMPT_VERSION,
    )


def create_preview_llm() -> PreviewLLM:
    return DeterministicPreviewLLM()


def build_structured_result_tool(
    *,
    target_title: str,
    resume_text: str,
    job_description: str,
    user_context: RecentAnalysisContext,
    llm_payload: dict[str, Any],
) -> AnalysisResult:
    base_output = MockAnalysisProvider().run(
        target_title=target_title,
        resume_text=resume_text,
        job_description=job_description,
    )
    result = base_output.result
    context_missing = [
        skill
        for skill in user_context.previous_missing_skills
        if skill not in {item.skill for item in result.missing_skills}
    ]
    if context_missing:
        result.resume_improvement_suggestions.extend(
            f"Previous analysis also flagged {skill}; show evidence of progress or remove unsupported claims."
            for skill in context_missing[:3]
        )
    if user_context.previous_project_suggestions:
        result.project_suggestions.append(
            "Build on prior advice: " + user_context.previous_project_suggestions[0]
        )
    result.project_tasks = result.project_tasks or build_project_tasks(target_title, result.missing_skills)
    result.resume_improvement_suggestions = (
        result.resume_improvement_suggestions or build_resume_suggestions(result.missing_skills)
    )
    if llm_payload.get("summary_hint"):
        result.summary = f"{result.summary} Experimental context note: {llm_payload['summary_hint']}."
    return AnalysisResult.model_validate(result.model_dump(by_alias=True))


def _run_graph_or_fallback(*, db: Session, state: PreviewState, llm: PreviewLLM) -> PreviewState:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return _run_fallback(db=db, state=state, llm=llm)

    graph = StateGraph(PreviewState)
    graph.add_node("load_inputs", lambda current: _load_inputs(db, current))
    graph.add_node("load_context", lambda current: _load_context(db, current))
    graph.add_node("call_llm", lambda current: _call_llm(llm, current))
    graph.add_node("validate_result", _validate_result)
    graph.set_entry_point("load_inputs")
    graph.add_edge("load_inputs", "load_context")
    graph.add_edge("load_context", "call_llm")
    graph.add_edge("call_llm", "validate_result")
    graph.add_edge("validate_result", END)
    return graph.compile().invoke(state)


def _run_fallback(*, db: Session, state: PreviewState, llm: PreviewLLM) -> PreviewState:
    state = _load_inputs(db, state)
    state = _load_context(db, state)
    state = _call_llm(llm, state)
    return _validate_result(state)


def _load_inputs(db: Session, state: PreviewState) -> PreviewState:
    state["resume_text"] = get_resume_text_tool(db, state["job_id"])
    state["job_description"] = get_job_description_tool(db, state["job_id"])
    state["intermediate_steps"]["tools"] = {
        "get_resume_text_tool": {"chars": len(state["resume_text"])},
        "get_job_description_tool": {"chars": len(state["job_description"])},
    }
    return state


def _load_context(db: Session, state: PreviewState) -> PreviewState:
    context = get_recent_user_analysis_context_tool(db, state["job_id"])
    state["user_context"] = context.model_dump()
    state["intermediate_steps"]["recent_user_analysis_context"] = state["user_context"]
    return state


def _call_llm(llm: PreviewLLM, state: PreviewState) -> PreviewState:
    prompt = _build_preview_prompt(state)
    response = llm.invoke(prompt)
    state["llm_payload"] = _coerce_llm_payload(response)
    state["intermediate_steps"]["llm_preview"] = {
        "prompt_chars": len(prompt),
        "payload_keys": sorted(state["llm_payload"].keys()),
    }
    return state


def _validate_result(state: PreviewState) -> PreviewState:
    context = RecentAnalysisContext.model_validate(state["user_context"])
    result = build_structured_result_tool(
        target_title=state["target_title"],
        resume_text=state["resume_text"],
        job_description=state["job_description"],
        user_context=context,
        llm_payload=state["llm_payload"],
    )
    state["result"] = result
    state["intermediate_steps"]["final_result_validation"] = {
        "validated_schema": "AnalysisResult",
        "writes_result_json": False,
    }
    return state


def _build_preview_prompt(state: PreviewState) -> str:
    return json.dumps(
        {
            "task": "OfferPath experimental LangChain/LangGraph preview",
            "target_title": state["target_title"],
            "resume_text": state.get("resume_text", "")[:4000],
            "job_description": state.get("job_description", "")[:4000],
            "recent_user_analysis_context": state.get("user_context", {}),
            "output": "Return structured hints only; backend validates into AnalysisResult.",
        },
        ensure_ascii=True,
    )


def _coerce_llm_payload(response: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        return {"summary_hint": response[:200]}
    return parsed if isinstance(parsed, dict) else {"summary_hint": str(parsed)[:200]}
