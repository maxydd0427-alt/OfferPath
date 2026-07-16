from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal, init_db
from app.models import User
from app.rag_v2.embedder import FakeEmbedder
from app.rag_v2.ingestion import RAGIngestionService

DEMO_OWNER_ID = 1

DOCUMENTS = [
    ("career_knowledge", "OfferPath project description", "Synthetic demo: OfferPath uses FastAPI, Redis workers, structured AI analysis, and a React frontend."),
    ("project_note", "AWS PDF Processing Pipeline description", "User-authored demo: S3 upload triggers workers that parse PDF files and store analysis metadata."),
    ("project_note", "FedPAIE project description", "User-authored demo: FedPAIE explores privacy-preserving AI evaluation and project evidence."),
    ("job_description", "Cloud Engineer job description", "Synthetic demo: Cloud engineer role needs AWS IAM, VPC networking, Docker, CI/CD, and incident response."),
    ("job_description", "SRE job description", "Synthetic demo: SRE role requires SLI, SLO, alerting, Kubernetes, Redis, and production debugging."),
    ("job_description", "AI Operations job description", "Synthetic demo: AI operations role needs LLM monitoring, Langfuse, prompt evaluation, and reliability playbooks."),
    ("career_knowledge", "Kubernetes learning notes", "Synthetic demo: Kubernetes notes cover deployments, services, probes, config maps, and troubleshooting pods."),
    ("career_knowledge", "RAG engineering notes", "Synthetic demo: RAG evaluation should track Recall@K, MRR, tenant isolation, reranking, and citation quality."),
    ("career_knowledge", "AWS networking and IAM notes", "Synthetic demo: AWS IAM least privilege, security groups, VPC routing, SQS, and S3 access patterns."),
    ("interview_note", "Interview record", "Synthetic demo: Interview feedback asked for clearer trade-offs, Redis queue reliability, and API testing evidence."),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = db.get(User, DEMO_OWNER_ID)
        if user is None:
            user = User(id=DEMO_OWNER_ID, email="demo@example.com", hashed_password="demo-only")
            db.add(user)
            db.commit()
        service = RAGIngestionService(embedder=FakeEmbedder())
        for source_type, title, text in DOCUMENTS:
            document = service.ingest_text(
                db,
                owner_id=DEMO_OWNER_ID,
                source_type=source_type,
                title=title,
                text_content=text,
                metadata={"demo": True, "data_label": "controlled synthetic or user-authored demo"},
            )
            print(f"{document.id}: {document.title} [{document.status}]")
    finally:
        db.close()


if __name__ == "__main__":
    main()
