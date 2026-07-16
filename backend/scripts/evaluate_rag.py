from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import RAGDocument
from app.rag_v2.embedder import FakeEmbedder
from app.rag_v2.reranker import FakeReranker
from app.rag_v2.retriever import OfferPathRetriever

CASES = [
    {"query": "AWS architecture IAM VPC S3", "owner_id": 1, "expected_title": "AWS networking and IAM notes"},
    {"query": "FastAPI Redis worker queue", "owner_id": 1, "expected_title": "OfferPath project description"},
    {"query": "Kubernetes deployment probes gap", "owner_id": 1, "expected_title": "Kubernetes learning notes"},
    {"query": "SRE SLI SLO alerting", "owner_id": 1, "expected_title": "SRE job description"},
    {"query": "RAG Recall@K MRR evaluation", "owner_id": 1, "expected_title": "RAG engineering notes"},
    {"query": "project evidence privacy AI evaluation", "owner_id": 1, "expected_title": "FedPAIE project description"},
    {"query": "cloud engineer target requirements", "owner_id": 1, "expected_title": "Cloud Engineer job description"},
    {"query": "quantum biology wet lab", "owner_id": 1, "expected_title": None},
    {"query": "中文 查询 AWS IAM 权限 网络", "owner_id": 1, "expected_title": "AWS networking and IAM notes"},
    {"query": "tenant isolation other user document", "owner_id": 2, "expected_title": None},
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        retriever = OfferPathRetriever(embedder=FakeEmbedder(), reranker=FakeReranker())
        rows = []
        for case in CASES:
            result = retriever.retrieve_for_analysis(
                db,
                owner_id=case["owner_id"],
                analysis_job_id=None,
                target_title=case["query"],
                job_description=case["query"],
            )
            titles = [citation.title for citation in result.citations]
            expected = case["expected_title"]
            rank = titles.index(expected) + 1 if expected in titles else None
            rows.append({"case": case, "titles": titles, "rank": rank, "latency_ms": result.latency_ms})

        answerable = [row for row in rows if row["case"]["expected_title"] is not None]
        recall_1 = _recall(answerable, 1)
        recall_3 = _recall(answerable, 3)
        recall_5 = _recall(answerable, 5)
        mrr = mean([(1 / row["rank"]) if row["rank"] else 0 for row in answerable]) if answerable else 0.0
        empty_rate = sum(1 for row in rows if not row["titles"]) / len(rows)
        tenant_case = next(row for row in rows if row["case"]["owner_id"] == 2)
        tenant_isolation = 1.0 if not tenant_case["titles"] else 0.0
        avg_latency = mean(row["latency_ms"] for row in rows)
        metrics = {
            "Recall@1": recall_1,
            "Recall@3": recall_3,
            "Recall@5": recall_5,
            "MRR": mrr,
            "Empty Retrieval Rate": empty_rate,
            "Tenant Isolation Pass Rate": tenant_isolation,
            "Average Retrieval Latency": avg_latency,
            "case_count": len(rows),
            "ready_document_count": db.scalar(select(RAGDocument).where(RAGDocument.status == "ready").count()) if False else None,
        }
        if args.json_output:
            print(json.dumps({"metrics": metrics, "cases": rows}, indent=2))
        else:
            for name, value in metrics.items():
                if value is not None:
                    print(f"{name}: {value:.4f}" if isinstance(value, float) else f"{name}: {value}")
    finally:
        db.close()


def _recall(rows: list[dict], k: int) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row["rank"] is not None and row["rank"] <= k) / len(rows)


if __name__ == "__main__":
    main()
