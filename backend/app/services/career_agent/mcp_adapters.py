from typing import Protocol

from pydantic import BaseModel, Field

from app.services.analysis import AnalysisResult


class GitHubReferenceProject(BaseModel):
    name: str
    url: str
    reason: str
    matched_skills: list[str] = Field(default_factory=list)


class NotionNoteDraft(BaseModel):
    title: str
    sections: list[str] = Field(default_factory=list)
    published: bool = False


class GmailDraft(BaseModel):
    subject: str
    body: str
    to: str | None = None
    sent: bool = False


class ExternalMCPAdapter(Protocol):
    def search_github_reference_projects(self, *, target_title: str, result: AnalysisResult) -> list[GitHubReferenceProject]:
        pass

    def draft_notion_learning_note(
        self,
        *,
        target_title: str,
        result: AnalysisResult,
        github_projects: list[GitHubReferenceProject],
    ) -> NotionNoteDraft:
        pass

    def draft_gmail_progress_update(
        self,
        *,
        target_title: str,
        result: AnalysisResult,
        github_projects: list[GitHubReferenceProject],
    ) -> GmailDraft:
        pass


class DeterministicMCPAdapter:
    """MCP-ready adapter with deterministic no-network behavior for tests and previews."""

    def search_github_reference_projects(self, *, target_title: str, result: AnalysisResult) -> list[GitHubReferenceProject]:
        focus_skills = [item.skill for item in result.missing_skills[:3]]
        if not focus_skills:
            focus_skills = result.matched_skills[:3] or ["backend", "testing", "deployment"]
        slug = "-".join(skill.lower().replace("/", "-").replace(" ", "-") for skill in focus_skills[:2])
        return [
            GitHubReferenceProject(
                name=f"{target_title} reference: {', '.join(focus_skills[:2])}",
                url=f"https://github.com/search?q={slug}+portfolio+project&type=repositories",
                reason="Search query draft for finding portfolio projects that match the roadmap gaps.",
                matched_skills=focus_skills,
            )
        ]

    def draft_notion_learning_note(
        self,
        *,
        target_title: str,
        result: AnalysisResult,
        github_projects: list[GitHubReferenceProject],
    ) -> NotionNoteDraft:
        roadmap_lines = [f"{item.days}: {item.skill} - {item.task}" for item in result.thirty_day_roadmap[:4]]
        project_lines = [f"{project.name}: {project.url}" for project in github_projects]
        return NotionNoteDraft(
            title=f"OfferPath roadmap - {target_title}",
            sections=[
                "Summary: " + result.summary,
                "30-day roadmap:\n" + "\n".join(roadmap_lines),
                "GitHub references:\n" + "\n".join(project_lines),
            ],
            published=False,
        )

    def draft_gmail_progress_update(
        self,
        *,
        target_title: str,
        result: AnalysisResult,
        github_projects: list[GitHubReferenceProject],
    ) -> GmailDraft:
        focus = ", ".join(item.skill for item in result.missing_skills[:3]) or "portfolio depth"
        references = "\n".join(f"- {project.name}: {project.url}" for project in github_projects)
        return GmailDraft(
            subject=f"OfferPath {target_title} roadmap update",
            body=(
                f"Current focus: {focus}\n\n"
                f"Roadmap summary:\n{result.summary}\n\n"
                f"Reference projects:\n{references}"
            ),
            sent=False,
        )


def create_mcp_adapter() -> ExternalMCPAdapter:
    return DeterministicMCPAdapter()
