def build_analysis_queries(*, target_title: str, job_description: str, resume_summary: str | None = None) -> list[str]:
    jd = " ".join(job_description.split())[:1200]
    resume = (" ".join((resume_summary or "").split())[:400]) or "current resume"
    return [
        f"Candidate evidence for {target_title}: {resume}",
        f"Target requirements for {target_title}: {jd}",
        f"Skill gaps and interview preparation for {target_title}: {jd} {resume}",
    ]
