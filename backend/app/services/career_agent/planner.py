from dataclasses import dataclass
import json
import ssl
from typing import Any, Protocol
import urllib.error
import urllib.request

from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings


@dataclass(frozen=True)
class ReActAction:
    thought: str
    tool_name: str


class AgentPlanner(Protocol):
    name: str

    def choose_next_action(
        self,
        *,
        state: dict[str, Any],
        observations: list[dict[str, Any]],
    ) -> ReActAction | None:
        pass


class PlannerConfigurationError(RuntimeError):
    pass


class PlannerDecisionError(RuntimeError):
    pass


class PlannerDecision(BaseModel):
    thought: str = Field(min_length=1)
    action: str = Field(min_length=1)


class PlannerLLMClient(Protocol):
    def generate_decision(self, prompt: str) -> dict[str, Any]:
        pass


class HeuristicAgentPlanner:
    """State-based planner that chooses the next safe tool dynamically."""

    name = "heuristic_state_planner"

    def choose_next_action(
        self,
        *,
        state: dict[str, Any],
        observations: list[dict[str, Any]],
    ) -> ReActAction | None:
        if not state["resume_text"]:
            return ReActAction(
                thought="I need resume evidence before reasoning about skill gaps.",
                tool_name="get_resume_text_tool",
            )
        if not state["job_description"]:
            return ReActAction(
                thought="I need the target JD before comparing the user's evidence to role expectations.",
                tool_name="get_job_description_tool",
            )
        if not state["user_context_loaded"]:
            return ReActAction(
                thought="I should check previous successful analyses to avoid giving isolated advice.",
                tool_name="get_recent_user_analysis_context_tool",
            )
        if state["rag_runtime"] != "disabled" and not state["rag_context_loaded"]:
            return ReActAction(
                thought="RAG is available, so I should retrieve user-scoped career memory before building the roadmap.",
                tool_name="retrieve_career_rag_context_tool",
            )
        if "result" not in state:
            return ReActAction(
                thought="I have enough internal and retrieved context to build a validated structured result.",
                tool_name="build_structured_result_tool",
            )
        if state["user_feedback"] and not state["feedback_used"]:
            return ReActAction(
                thought="The user gave feedback, so I should revise the roadmap before external project references.",
                tool_name="revise_roadmap_with_user_feedback_tool",
            )
        if not state["github_reference_projects"]:
            return ReActAction(
                thought="The roadmap needs concrete reference projects, so I should search GitHub through the safe MCP adapter.",
                tool_name="github_mcp_search_reference_projects",
            )
        if state["notion_note_draft"] is None:
            return ReActAction(
                thought="The user needs a persistent learning view, so I should draft a Notion note without publishing.",
                tool_name="notion_mcp_draft_learning_note",
            )
        if state["gmail_draft"] is None:
            return ReActAction(
                thought="The user may want a progress update, so I should prepare a Gmail draft without sending.",
                tool_name="gmail_mcp_draft_progress_update",
            )
        return None


class LLMReActPlanner:
    """LLM-driven planner for orthodox bounded ReAct tool selection."""

    name = "llm_react_planner"

    def __init__(
        self,
        *,
        client: PlannerLLMClient | None = None,
        allowed_tools: list[str] | None = None,
    ) -> None:
        self.client = client or GeminiPlannerClient()
        self.allowed_tools = allowed_tools or []

    def choose_next_action(
        self,
        *,
        state: dict[str, Any],
        observations: list[dict[str, Any]],
    ) -> ReActAction | None:
        prompt = _build_planner_prompt(
            state=state,
            observations=observations,
            allowed_tools=self.allowed_tools,
        )
        try:
            decision = PlannerDecision.model_validate(self.client.generate_decision(prompt))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise PlannerDecisionError(f"LLM planner returned invalid decision JSON: {exc}") from exc

        action = decision.action.strip()
        if action == "finish":
            return None
        if action not in self.allowed_tools:
            raise PlannerDecisionError(f"LLM planner selected unsupported tool: {action}")
        return ReActAction(thought=decision.thought.strip(), tool_name=action)


class GeminiPlannerClient:
    def generate_decision(self, prompt: str) -> dict[str, Any]:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise PlannerConfigurationError("missing API key: set OFFERPATH_GEMINI_API_KEY to use the LLM planner")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20, context=_ssl_context()) as response:
                response_body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise PlannerDecisionError(f"LLM planner request failed with HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise PlannerDecisionError(f"LLM planner request failed: {exc}") from exc

        text = (
            response_body.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text")
        )
        if not isinstance(text, str) or not text.strip():
            raise PlannerDecisionError("LLM planner response did not include JSON text")
        return json.loads(text)


def create_agent_planner(
    *,
    allowed_tools: list[str],
    client: PlannerLLMClient | None = None,
) -> AgentPlanner:
    planner_name = get_settings().agent_planner.lower()
    if planner_name == "llm":
        return LLMReActPlanner(client=client, allowed_tools=allowed_tools)
    if planner_name == "heuristic":
        return HeuristicAgentPlanner()
    raise PlannerConfigurationError(f"Unsupported agent planner: {get_settings().agent_planner}")


def _build_planner_prompt(
    *,
    state: dict[str, Any],
    observations: list[dict[str, Any]],
    allowed_tools: list[str],
) -> str:
    safe_state = {
        "target_title": state["target_title"],
        "has_resume_text": bool(state["resume_text"]),
        "has_job_description": bool(state["job_description"]),
        "user_context_loaded": state["user_context_loaded"],
        "rag_runtime": state["rag_runtime"],
        "rag_context_loaded": state["rag_context_loaded"],
        "has_structured_result": "result" in state,
        "has_user_feedback": bool(state["user_feedback"]),
        "feedback_used": state["feedback_used"],
        "github_reference_count": len(state["github_reference_projects"]),
        "has_notion_note_draft": state["notion_note_draft"] is not None,
        "has_gmail_draft": state["gmail_draft"] is not None,
    }
    recent_observations = [
        {
            "tool": observation.get("tool"),
            "observation_keys": sorted((observation.get("observation") or {}).keys()),
        }
        for observation in observations[-5:]
    ]
    return (
        "You are the OfferPath career agent planner.\n"
        "Choose exactly one next tool call, or choose finish when the career analysis workflow is complete.\n"
        "You must obey these safety rules:\n"
        "- Only choose a tool from the allowed_tools list.\n"
        "- Never invent tools.\n"
        "- Notion and Gmail tools are draft-only; never ask to publish or send.\n"
        "- Prefer gathering resume, JD, prior context, and RAG context before building the result.\n"
        "- Build a structured result before GitHub, Notion, or Gmail actions.\n"
        "Return only JSON in this shape: {\"thought\": \"...\", \"action\": \"tool_name_or_finish\"}.\n\n"
        f"allowed_tools: {json.dumps(allowed_tools)}\n"
        f"state: {json.dumps(safe_state)}\n"
        f"recent_observations: {json.dumps(recent_observations)}\n"
    )


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:  # pragma: no cover
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())
