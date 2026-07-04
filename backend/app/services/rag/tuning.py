from pydantic import BaseModel, Field

from app.services.rag.retrieval_models import CareerRAGContext


class RAGTuningRecommendation(BaseModel):
    code: str
    severity: str = "info"
    reason: str
    action: str


class RAGTuningReport(BaseModel):
    latency_target_ms: float = 500
    min_retrieved_items: int = 3
    recommendations: list[RAGTuningRecommendation] = Field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return any(item.severity in {"warning", "critical"} for item in self.recommendations)


def build_rag_tuning_report(
    context: CareerRAGContext,
    *,
    latency_target_ms: float = 500,
    min_retrieved_items: int = 3,
    low_score_threshold: float = 0.4,
) -> RAGTuningReport:
    report = RAGTuningReport(
        latency_target_ms=latency_target_ms,
        min_retrieved_items=min_retrieved_items,
    )

    if not context.enabled:
        report.recommendations.append(
            RAGTuningRecommendation(
                code="rag_disabled",
                severity="warning",
                reason=context.error or "RAG retriever is not configured.",
                action="Configure OFFERPATH_BEDROCK_KB_ID and AWS credentials before relying on RAG context.",
            )
        )
        return report

    if context.error:
        report.recommendations.append(
            RAGTuningRecommendation(
                code="retrieval_error",
                severity="critical",
                reason=context.error,
                action="Check Bedrock KB id, IAM permissions, region, and data-source sync status.",
            )
        )

    if context.search_type.upper() != "HYBRID":
        report.recommendations.append(
            RAGTuningRecommendation(
                code="enable_hybrid_search",
                severity="warning",
                reason=f"Current search type is {context.search_type}, which may miss exact terms like AWS or Kubernetes.",
                action="Set OFFERPATH_BEDROCK_KB_SEARCH_TYPE=HYBRID for mixed semantic and keyword retrieval.",
            )
        )

    if context.metadata_filter != {"equals": {"key": "user_id", "value": context.user_id}}:
        report.recommendations.append(
            RAGTuningRecommendation(
                code="metadata_filter_mismatch",
                severity="critical",
                reason="Retrieval filter does not exactly match the required user_id tenant boundary.",
                action="Enforce equals(user_id, current_user_id) for every Bedrock KB request.",
            )
        )

    if context.latency_ms is not None and context.latency_ms > latency_target_ms:
        report.recommendations.append(
            RAGTuningRecommendation(
                code="high_latency",
                severity="warning",
                reason=f"Retrieval latency {context.latency_ms:.1f}ms exceeded target {latency_target_ms:.1f}ms.",
                action="Check CloudWatch P95, reduce numberOfResults, cache stable queries, or verify the app and KB are in the same region.",
            )
        )

    if not context.items:
        report.recommendations.append(
            RAGTuningRecommendation(
                code="empty_retrieval",
                severity="warning",
                reason="Bedrock KB returned no usable context.",
                action="Verify S3 sync, user_id metadata, document chunking, and query construction; keep HYBRID search enabled.",
            )
        )
        return report

    if len(context.items) < min_retrieved_items:
        report.recommendations.append(
            RAGTuningRecommendation(
                code="low_recall",
                severity="info",
                reason=f"Only {len(context.items)} item(s) were retrieved; target is at least {min_retrieved_items}.",
                action="Increase numberOfResults, add more user notes/JDs, or broaden the retrieval query with role and skill synonyms.",
            )
        )

    scored_items = [item for item in context.items if item.score is not None]
    if scored_items and max(item.score or 0 for item in scored_items) < low_score_threshold:
        report.recommendations.append(
            RAGTuningRecommendation(
                code="low_similarity",
                severity="info",
                reason=f"Top retrieval score is below {low_score_threshold}.",
                action="Improve chunk quality, add metadata such as document_type and target_role, and expand queries with core skill keywords.",
            )
        )

    return report
