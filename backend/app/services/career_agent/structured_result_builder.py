from typing import Any

from app.services.career_agent.tools import RecentAnalysisContext
from app.services.analysis import (
    AnalysisResult,
    MockAnalysisProvider,
    build_project_tasks,
    build_resume_suggestions,
)


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
        result.summary = f"{result.summary} Agent context note: {llm_payload['summary_hint']}."
    rag_items = llm_payload.get("rag_context_items")
    if isinstance(rag_items, list) and rag_items:
        top_text = _rag_text_preview(rag_items[0])
        if top_text:
            result.summary = f"{result.summary} RAG context used: {top_text}."
        source_uri = _rag_source_uri(rag_items[0])
        if source_uri:
            result.project_suggestions.append(f"Use retrieved reference context as project guidance: {source_uri}")
        result.resume_improvement_suggestions.append(
            "Align roadmap evidence with retrieved career memory, market JD signals, and learning notes."
        )
    if llm_payload.get("user_feedback"):
        feedback = str(llm_payload["user_feedback"]).strip()
        result.summary = f"{result.summary} Roadmap revision feedback applied: {feedback}."
        result.project_suggestions.append(f"Revise the roadmap around this user feedback: {feedback}")
        result.resume_improvement_suggestions.append(f"Reflect this preference in the next resume/project iteration: {feedback}")
    return AnalysisResult.model_validate(result.model_dump(by_alias=True))


def _rag_text_preview(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    text = item.get("text")
    if not isinstance(text, str):
        return ""
    return " ".join(text.split())[:180]


def _rag_source_uri(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    source_uri = item.get("source_uri")
    return source_uri if isinstance(source_uri, str) and source_uri else None
