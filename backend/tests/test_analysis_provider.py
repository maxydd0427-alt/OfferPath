import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.services.analysis import AnalysisResult, GeminiAnalysisProvider, MissingAPIKeyError, MockAnalysisProvider


def test_mock_provider_returns_extended_schema() -> None:
    output = MockAnalysisProvider().run(
        target_title="AI SRE",
        resume_text="Python FastAPI Docker testing",
        job_description=(
            "We need Python, FastAPI, Redis, AWS, SQS, S3, Docker, Kubernetes, "
            "observability, incident response, testing, and REST APIs."
        ),
    )

    payload = output.result.model_dump(by_alias=True)

    assert output.ai_provider == "mock"
    assert payload["matched_skills"]
    assert payload["missing_skills"]
    assert all("priority" in item for item in payload["missing_skills"])
    assert "30_day_roadmap" in payload
    assert payload["project_tasks"]
    assert payload["interview_talking_points"]
    assert payload["resume_improvement_suggestions"]
    assert "final_result_validation" in output.intermediate_steps


def test_gemini_provider_raises_clear_error_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OFFERPATH_AI_PROVIDER", "gemini")
    monkeypatch.setenv("OFFERPATH_GEMINI_API_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(MissingAPIKeyError, match="OFFERPATH_GEMINI_API_KEY"):
        GeminiAnalysisProvider().run(
            target_title="Backend Engineer",
            resume_text="Python FastAPI",
            job_description="We need Python, FastAPI, Redis, AWS, Docker, testing, and REST APIs.",
        )

    get_settings.cache_clear()


def test_invalid_ai_output_is_rejected_by_pydantic() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {
                "resume_skills": ["python"],
                "target_role_skills": ["python", "redis"],
                "summary": "Needs Redis depth.",
                "missing_skills": [{"skill": "redis", "priority": "urgent", "reason": "Required by JD"}],
            }
        )
