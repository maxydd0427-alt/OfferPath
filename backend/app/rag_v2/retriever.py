import logging
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.models import RAGRun, utc_now
from app.rag_v2.context_builder import build_citations, build_context
from app.rag_v2.embedder import Embedder, create_embedder
from app.rag_v2.hybrid_search import reciprocal_rank_fusion
from app.rag_v2.keyword_search import keyword_search
from app.rag_v2.query_builder import build_analysis_queries
from app.rag_v2.reranker import Reranker, create_reranker
from app.rag_v2.schemas import RetrievalCandidate, RetrievalResult
from app.rag_v2.vector_search import vector_search

logger = get_logger(__name__)


class OfferPathRetriever:
    def __init__(self, embedder: Embedder | None = None, reranker: Reranker | None = None) -> None:
        self.embedder = embedder or create_embedder()
        self.reranker = reranker or create_reranker()

    def retrieve_for_analysis(
        self,
        db: Session,
        *,
        owner_id: int,
        analysis_job_id: int | None,
        target_title: str,
        job_description: str,
        source_types: list[str] | None = None,
    ) -> RetrievalResult:
        settings = get_settings()
        started = time.perf_counter()
        query = f"{target_title}\n{job_description[:2000]}"
        rewritten_queries = build_analysis_queries(
            target_title=target_title,
            job_description=job_description,
            resume_summary=target_title,
        )
        try:
            all_candidates: dict[int, RetrievalCandidate] = {}
            for rewritten_query in rewritten_queries:
                embedding = self.embedder.embed_query(rewritten_query)
                vector_results = vector_search(
                    db,
                    owner_id,
                    embedding,
                    settings.rag_vector_limit,
                    source_types=source_types,
                )
                keyword_results = keyword_search(
                    db,
                    owner_id,
                    rewritten_query,
                    settings.rag_keyword_limit,
                    source_types=source_types,
                )
                fused = reciprocal_rank_fusion(vector_results, keyword_results, settings.rag_hybrid_limit)
                for candidate in fused:
                    existing = all_candidates.get(candidate.chunk_id)
                    if existing is None or float(candidate.hybrid_score or 0) > float(existing.hybrid_score or 0):
                        all_candidates[candidate.chunk_id] = candidate
            merged = sorted(
                all_candidates.values(),
                key=lambda item: (-float(item.hybrid_score or 0), item.chunk_id),
            )
            selected = self.reranker.rerank(query, merged, settings.rag_final_limit)
            citations = build_citations(selected)
            context = build_context(citations, settings.rag_max_context_chars) if citations else ""
            latency_ms = int((time.perf_counter() - started) * 1000)
            result = RetrievalResult(
                query=query,
                rewritten_queries=rewritten_queries,
                citations=citations,
                context=context,
                retrieved_chunk_ids=[candidate.chunk_id for candidate in merged],
                selected_chunk_ids=[candidate.chunk_id for candidate in selected],
                latency_ms=latency_ms,
                status="succeeded",
                pipeline_version=settings.rag_pipeline_version,
            )
            self._persist_run(db, owner_id, analysis_job_id, result)
            return result
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            result = RetrievalResult(
                query=query,
                rewritten_queries=rewritten_queries,
                citations=[],
                context="",
                latency_ms=latency_ms,
                status="failed",
                error_message=str(exc)[:1000],
                pipeline_version=settings.rag_pipeline_version,
            )
            self._persist_run(db, owner_id, analysis_job_id, result)
            return result

    def _persist_run(
        self,
        db: Session,
        owner_id: int,
        analysis_job_id: int | None,
        result: RetrievalResult,
    ) -> None:
        run = RAGRun(
            owner_id=owner_id,
            analysis_job_id=analysis_job_id,
            query=result.query,
            rewritten_queries=result.rewritten_queries,
            retrieved_chunk_ids=result.retrieved_chunk_ids,
            selected_chunk_ids=result.selected_chunk_ids,
            latency_ms=result.latency_ms,
            retrieved_count=len(result.retrieved_chunk_ids),
            selected_count=len(result.selected_chunk_ids),
            status=result.status,
            error_message=result.error_message,
            pipeline_version=result.pipeline_version,
            created_at=utc_now(),
        )
        db.add(run)
        db.commit()
        log_event(
            logger,
            logging.INFO,
            "rag_v2.run",
            rag_run_id=run.id,
            owner_id=owner_id,
            analysis_job_id=analysis_job_id,
            retrieved_count=run.retrieved_count,
            selected_count=run.selected_count,
            latency_ms=run.latency_ms,
            status=run.status,
            pipeline_version=run.pipeline_version,
        )
