from typing import Any, Protocol

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
    external_id: str | None = None
    url: str | None = None


class GmailDraft(BaseModel):
    subject: str
    body: str
    to: str | None = None
    sent: bool = False
    external_id: str | None = None


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


class MCPToolClient(Protocol):
    """Small runtime boundary for real MCP servers.

    The FastAPI backend should provide an implementation that can call the
    configured GitHub, Notion, and Gmail MCP servers. Tests can provide a fake.
    """

    def call_tool(self, server: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        pass


class MCPAdapterConfig(BaseModel):
    github_server: str = "github"
    github_search_tool: str = "search_repositories"
    notion_server: str = "notion"
    notion_draft_tool: str = "create_page_draft"
    gmail_server: str = "gmail"
    gmail_create_draft_tool: str = "create_draft"


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


class MCPExternalAdapter:
    """Adapter that maps OfferPath-safe actions to real MCP tool calls."""

    def __init__(
        self,
        client: MCPToolClient,
        config: MCPAdapterConfig | None = None,
    ) -> None:
        self.client = client
        self.config = config or MCPAdapterConfig()

    def search_github_reference_projects(self, *, target_title: str, result: AnalysisResult) -> list[GitHubReferenceProject]:
        focus_skills = [item.skill for item in result.missing_skills[:4]]
        if not focus_skills:
            focus_skills = result.matched_skills[:4] or ["backend", "testing", "deployment"]
        response = self.client.call_tool(
            self.config.github_server,
            self.config.github_search_tool,
            {
                "query": _github_query(target_title, focus_skills),
                "limit": 5,
                "safe_mode": "read_only",
                "focus_skills": focus_skills,
            },
        )
        return _parse_github_projects(response, fallback_skills=focus_skills)

    def draft_notion_learning_note(
        self,
        *,
        target_title: str,
        result: AnalysisResult,
        github_projects: list[GitHubReferenceProject],
    ) -> NotionNoteDraft:
        draft = DeterministicMCPAdapter().draft_notion_learning_note(
            target_title=target_title,
            result=result,
            github_projects=github_projects,
        )
        response = self.client.call_tool(
            self.config.notion_server,
            self.config.notion_draft_tool,
            {
                "title": draft.title,
                "sections": draft.sections,
                "published": False,
                "safe_mode": "draft_only",
            },
        )
        response_dict = _as_dict(response)
        return NotionNoteDraft(
            title=str(response_dict.get("title") or draft.title),
            sections=_string_list(response_dict.get("sections")) or draft.sections,
            published=bool(response_dict.get("published", False)),
            external_id=_optional_str(response_dict.get("id") or response_dict.get("external_id")),
            url=_optional_str(response_dict.get("url")),
        )

    def draft_gmail_progress_update(
        self,
        *,
        target_title: str,
        result: AnalysisResult,
        github_projects: list[GitHubReferenceProject],
    ) -> GmailDraft:
        draft = DeterministicMCPAdapter().draft_gmail_progress_update(
            target_title=target_title,
            result=result,
            github_projects=github_projects,
        )
        response = self.client.call_tool(
            self.config.gmail_server,
            self.config.gmail_create_draft_tool,
            {
                "subject": draft.subject,
                "body": draft.body,
                "to": draft.to,
                "send": False,
                "safe_mode": "draft_only",
            },
        )
        response_dict = _as_dict(response)
        return GmailDraft(
            subject=str(response_dict.get("subject") or draft.subject),
            body=str(response_dict.get("body") or draft.body),
            to=_optional_str(response_dict.get("to") or draft.to),
            sent=bool(response_dict.get("sent", False)),
            external_id=_optional_str(response_dict.get("id") or response_dict.get("external_id")),
        )


def create_mcp_adapter(
    client: MCPToolClient | None = None,
    config: MCPAdapterConfig | None = None,
) -> ExternalMCPAdapter:
    if client is None:
        return DeterministicMCPAdapter()
    return MCPExternalAdapter(client=client, config=config)


def _github_query(target_title: str, focus_skills: list[str]) -> str:
    terms = " ".join(focus_skills[:4])
    return f"{target_title} portfolio project {terms}".strip()


def _parse_github_projects(response: Any, *, fallback_skills: list[str]) -> list[GitHubReferenceProject]:
    payload = _as_dict(response)
    raw_items = payload.get("items") or payload.get("repositories") or payload.get("projects") or response
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if not isinstance(raw_items, list):
        return []

    projects: list[GitHubReferenceProject] = []
    for item in raw_items[:5]:
        if not isinstance(item, dict):
            continue
        name = item.get("full_name") or item.get("name") or item.get("title")
        url = item.get("html_url") or item.get("url")
        if not isinstance(name, str) or not isinstance(url, str):
            continue
        description = item.get("description")
        projects.append(
            GitHubReferenceProject(
                name=name,
                url=url,
                reason=str(description or "Reference project returned by GitHub MCP search."),
                matched_skills=_string_list(item.get("matched_skills")) or fallback_skills[:3],
            )
        )
    return projects


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
