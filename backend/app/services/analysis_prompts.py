def build_gemini_prompt(target_title: str, resume_text: str, job_description: str) -> str:
    return f"""
You are the analysis workflow for OfferPath.
Return only valid JSON matching this exact schema:
{{
  "resume_skills": ["string"],
  "target_role_skills": ["string"],
  "missing_skills": ["string"],
  "summary": "string",
  "roadmap": [{{"priority": "P1", "skill": "string", "task": "string"}}],
  "project_suggestions": ["string"],
  "interview_questions": ["string"]
}}

Workflow:
1. Understand the resume.
2. Understand the job description.
3. Compare skill gaps.
4. Generate a prioritized roadmap.
5. Suggest proof-oriented projects.
6. Generate interview preparation questions.

Target title:
{target_title}

Resume:
{resume_text}

Job description:
{job_description}
""".strip()
