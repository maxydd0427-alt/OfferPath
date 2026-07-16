from app.core.config import get_settings
from app.rag_v2.schemas import RetrievalCandidate


def reciprocal_rank_fusion(
    vector_results: list[RetrievalCandidate],
    keyword_results: list[RetrievalCandidate],
    limit: int,
) -> list[RetrievalCandidate]:
    rrf_k = get_settings().rag_rrf_k
    merged: dict[int, RetrievalCandidate] = {}
    scores: dict[int, float] = {}
    for rank, candidate in enumerate(vector_results, start=1):
        merged[candidate.chunk_id] = candidate
        scores[candidate.chunk_id] = scores.get(candidate.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    for rank, candidate in enumerate(keyword_results, start=1):
        existing = merged.get(candidate.chunk_id)
        if existing:
            merged[candidate.chunk_id] = existing.model_copy(update={"keyword_score": candidate.keyword_score})
        else:
            merged[candidate.chunk_id] = candidate
        scores[candidate.chunk_id] = scores.get(candidate.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    fused = [
        candidate.model_copy(update={"hybrid_score": scores[candidate.chunk_id]})
        for candidate in merged.values()
    ]
    return sorted(fused, key=lambda item: (-float(item.hybrid_score or 0), item.chunk_id))[:limit]
