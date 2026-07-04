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
        result.summary = f"{result.summary} Experimental context note: {llm_payload['summary_hint']}."
    if llm_payload.get("user_feedback"):
        feedback = str(llm_payload["user_feedback"]).strip()
        result.summary = f"{result.summary} Roadmap revision feedback applied: {feedback}."
        result.project_suggestions.append(f"Revise the roadmap around this user feedback: {feedback}")
        result.resume_improvement_suggestions.append(f"Reflect this preference in the next resume/project iteration: {feedback}")
    return AnalysisResult.model_validate(result.model_dump(by_alias=True))
