def build_gemini_step_prompt(
    *,
    step: str,
    target_title: str,
    resume_text: str,
    job_description: str,
    context: dict | None = None,
) -> str:
    context_block = f"\nPrior workflow context JSON:\n{context}\n" if context else ""
    return f"""
You are OfferPath's backend AI career analysis workflow.
Return only valid JSON. Do not wrap the JSON in markdown.

Optimize the analysis for practical engineering roles such as AI SRE,
backend engineer, cloud engineer, and AI agent engineer. Prefer concrete
evidence, measurable project tasks, production systems thinking, reliability,
cloud, observability, queues, deployment, testing, and AI workflow skills.

Current workflow step:
{step}

Target title:
{target_title}

Resume text:
{resume_text}

Job description:
{job_description}
{context_block}
Step output requirements:
{_step_schema(step)}
""".strip()


def build_gemini_validation_prompt(
    *,
    target_title: str,
    resume_text: str,
    job_description: str,
    context: dict,
) -> str:
    return build_gemini_step_prompt(
        step="final_result_validation",
        target_title=target_title,
        resume_text=resume_text,
        job_description=job_description,
        context=context,
    )


def _step_schema(step: str) -> str:
    schemas = {
        "resume_understanding": """
{
  "resume_skills": ["skill name"],
  "weak_skills": ["skill that is mentioned but not strongly proven"],
  "evidence_from_resume": ["short resume evidence quote or paraphrase"],
  "summary": "brief resume capability summary"
}
""",
        "jd_understanding": """
{
  "target_role_skills": ["skill name"],
  "evidence_from_jd": ["short JD requirement quote or paraphrase"],
  "role_focus": "what this role mainly needs"
}
""",
        "skill_gap_comparison": """
{
  "matched_skills": ["skill name"],
  "partially_matched_skills": ["skill name"],
  "missing_skills": [
    {"skill": "skill name", "priority": "P1|P2|P3", "reason": "why it matters"}
  ],
  "summary": "gap summary"
}
""",
        "roadmap_generation": """
{
  "30_day_roadmap": [
    {"priority": "P1", "skill": "skill name", "task": "specific action", "days": "Day 1-7"}
  ],
  "resume_improvement_suggestions": ["specific resume improvement"]
}
""",
        "project_recommendation": """
{
  "project_tasks": [
    {"title": "task title", "description": "what to build", "skills": ["skill name"], "success_metric": "how to prove it works"}
  ],
  "project_suggestions": ["portfolio project direction"]
}
""",
        "interview_preparation": """
{
  "interview_questions": ["likely interview question"],
  "interview_talking_points": ["specific story or point to prepare"]
}
""",
        "final_result_validation": """
Return one final JSON object matching this exact schema:
{
  "resume_skills": ["string"],
  "target_role_skills": ["string"],
  "matched_skills": ["string"],
  "weak_skills": ["string"],
  "partially_matched_skills": ["string"],
  "missing_skills": [
    {"skill": "string", "priority": "P1|P2|P3", "reason": "string"}
  ],
  "evidence_from_resume": ["string"],
  "evidence_from_jd": ["string"],
  "summary": "string",
  "30_day_roadmap": [
    {"priority": "P1", "skill": "string", "task": "string", "days": "string"}
  ],
  "roadmap": [
    {"priority": "P1", "skill": "string", "task": "string"}
  ],
  "project_tasks": [
    {"title": "string", "description": "string", "skills": ["string"], "success_metric": "string"}
  ],
  "project_suggestions": ["string"],
  "interview_questions": ["string"],
  "interview_talking_points": ["string"],
  "resume_improvement_suggestions": ["string"]
}
""",
    }
    return schemas[step].strip()
