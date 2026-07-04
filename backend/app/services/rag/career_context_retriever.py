from typing import Protocol

from sqlalchemy.orm import Session

from app.models import AnalysisJob
from app.services.rag.bedrock_kb_client import RAGConfigurationError, RAGRetrievalError
from app.services.rag.retrieval_models import CareerRAGContext


class CareerContextRetriever(Protocol):
    def retrieve(self, *, query: str, user_id: int | str, number_of_results: int | None = None) -> CareerRAGContext:
        pass


def retrieve_career_context_tool(
    db: Session,
    job_id: int,
    retriever: CareerContextRetriever | None,
) -> CareerRAGContext:
    job = db.get(AnalysisJob, job_id)
    if job is None:
        raise ValueError(f"AnalysisJob {job_id} not found")

    query = _build_career_query(job)
    if retriever is None:
        return CareerRAGContext(
            query=query,
            user_id=str(job.owner_id),
            items=[],
            metadata_filter={"equals": {"key": "user_id", "value": str(job.owner_id)}},
            enabled=False,
            error="RAG retriever is not configured.",
        )

    try:
        return retriever.retrieve(query=query, user_id=job.owner_id)
    except (RAGConfigurationError, RAGRetrievalError) as exc:
        return CareerRAGContext(
            query=query,
            user_id=str(job.owner_id),
            items=[],
            metadata_filter={"equals": {"key": "user_id", "value": str(job.owner_id)}},
            enabled=False,
            error=str(exc),
        )


def _build_career_query(job: AnalysisJob) -> str:
    jd_preview = " ".join(job.job_description.split())[:800]
    return f"Target role: {job.target_title}\nJob description: {jd_preview}"
