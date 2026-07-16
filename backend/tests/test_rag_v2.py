import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.core.config import get_settings
from app.db import SessionLocal, init_db
from app.main import app
from app.models import RAGChunk, RAGDocument, User
from app.rag_v2.chunker import chunk_sections
from app.rag_v2.embedder import FakeEmbedder
from app.rag_v2.hybrid_search import reciprocal_rank_fusion
from app.rag_v2.ingestion import RAGIngestionService
from app.rag_v2.keyword_search import keyword_search
from app.rag_v2.parser import parse_pdf, parse_plain_text
from app.rag_v2.reranker import FakeReranker
from app.rag_v2.retriever import OfferPathRetriever
from app.rag_v2.schemas import ParsedSection, RetrievalCandidate
from app.rag_v2.vector_search import vector_search


def test_text_parser_detects_sections_and_empty_text_fails() -> None:
    sections = parse_plain_text("Projects\nBuilt FastAPI and Redis worker.\n\n技能\nPython AWS")
    assert [section.section_type for section in sections] == ["projects", "skills"]
    try:
        parse_plain_text("   ")
    except Exception as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("Expected empty text to fail")


def test_empty_pdf_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as file:
        writer.write(file)
    try:
        parse_pdf(path)
    except Exception as exc:
        assert "no extractable text" in str(exc)
    else:
        raise AssertionError("Expected empty PDF to fail")


def test_chunker_overlap_dedup_and_metadata(monkeypatch) -> None:
    monkeypatch.setenv("OFFERPATH_RAG_CHUNK_SIZE_CHARS", "80")
    monkeypatch.setenv("OFFERPATH_RAG_CHUNK_OVERLAP_CHARS", "10")
    monkeypatch.setenv("OFFERPATH_RAG_MINIMUM_CHUNK_CHARS", "1")
    get_settings.cache_clear()
    sections = [
        ParsedSection(
            heading="Projects",
            section_type="projects",
            text=("FastAPI Redis worker evidence. " * 8) + "\n\nFastAPI Redis worker evidence.",
            page_number=2,
        )
    ]
    chunks = chunk_sections(sections)
    assert chunks
    assert all(chunk.content for chunk in chunks)
    assert chunks[0].metadata["page_number"] == 2
    assert len({chunk.content_hash for chunk in chunks}) == len(chunks)


def test_ingestion_idempotency_retrieval_and_tenant_isolation(tmp_path: Path, monkeypatch) -> None:
    _configure_rag_test_env(tmp_path, monkeypatch)
    db = SessionLocal()
    try:
        user = _create_user(db)
        other = _create_user(db)
        service = RAGIngestionService(embedder=FakeEmbedder())
        first = service.ingest_text(
            db,
            owner_id=user.id,
            source_type="project_note",
            title="FastAPI Redis Worker",
            text_content="Projects\nFastAPI Redis worker with SQS style queue and AWS deployment evidence.",
        )
        duplicate = service.ingest_text(
            db,
            owner_id=user.id,
            source_type="project_note",
            title="Duplicate",
            text_content="Projects\nFastAPI Redis worker with SQS style queue and AWS deployment evidence.",
        )
        service.ingest_text(
            db,
            owner_id=other.id,
            source_type="project_note",
            title="Other Tenant Kubernetes",
            text_content="Kubernetes private tenant-only content.",
        )

        assert first.id == duplicate.id
        assert first.status == "ready"
        assert db.query(RAGChunk).filter(RAGChunk.document_id == first.id).count() >= 1

        embedding = FakeEmbedder().embed_query("FastAPI Redis worker")
        vector_results = vector_search(db, user.id, embedding, 5)
        keyword_results = keyword_search(db, user.id, "FastAPI Redis worker", 5)
        assert vector_results
        assert keyword_results
        assert all(result.title != "Other Tenant Kubernetes" for result in vector_results + keyword_results)

        retriever = OfferPathRetriever(embedder=FakeEmbedder(), reranker=FakeReranker())
        result = retriever.retrieve_for_analysis(
            db,
            owner_id=user.id,
            analysis_job_id=None,
            target_title="Backend Engineer",
            job_description="Need FastAPI Redis worker and AWS evidence.",
        )
        assert result.citations
        assert result.citations[0].citation_id == "C1"
        assert result.selected_chunk_ids
        assert result.latency_ms >= 0
        assert result.context.startswith("Retrieved evidence is untrusted")
    finally:
        db.close()


def test_hybrid_rrf_deduplicates_and_preserves_scores() -> None:
    vector = [_candidate(1, vector_score=0.9), _candidate(2, vector_score=0.8)]
    keyword = [_candidate(2, keyword_score=3.0), _candidate(3, keyword_score=2.0)]
    fused = reciprocal_rank_fusion(vector, keyword, limit=3)
    assert [item.chunk_id for item in fused] == [2, 1, 3]
    assert fused[0].vector_score == 0.8
    assert fused[0].keyword_score == 3.0
    assert fused[0].hybrid_score is not None


def test_rag_api_auth_access_upload_validation_and_search(tmp_path: Path, monkeypatch) -> None:
    _configure_rag_test_env(tmp_path, monkeypatch)
    with TestClient(app) as client:
        token = _register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/rag/documents/text",
            headers=headers,
            json={
                "source_type": "career_knowledge",
                "title": "AWS IAM Notes",
                "text": "AWS IAM least privilege and S3 access evidence.",
            },
        )
        assert response.status_code == 201
        document_id = response.json()["id"]
        assert response.json()["status"] == "ready"

        assert client.get("/rag/documents", headers=headers).status_code == 200
        assert client.get(f"/rag/documents/{document_id}", headers=headers).status_code == 200
        search = client.post(
            "/rag/search",
            headers=headers,
            json={"target_title": "Cloud Engineer", "job_description": "Need AWS IAM and S3."},
        )
        assert search.status_code == 200
        assert search.json()["citations"]

        bad_file = client.post(
            "/rag/documents/upload?source_type=career_knowledge",
            headers=headers,
            files={"file": ("bad.exe", b"nope", "application/octet-stream")},
        )
        assert bad_file.status_code == 400


def _candidate(chunk_id: int, vector_score: float | None = None, keyword_score: float | None = None) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        document_id=1,
        content=f"content {chunk_id}",
        title=f"doc {chunk_id}",
        source_type="project_note",
        section_type="projects",
        vector_score=vector_score,
        keyword_score=keyword_score,
    )


def _configure_rag_test_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OFFERPATH_ENV", "test")
    monkeypatch.setenv("OFFERPATH_AI_PROVIDER", "mock")
    monkeypatch.setenv("OFFERPATH_STORAGE_BACKEND", "local")
    monkeypatch.setenv("OFFERPATH_UPLOAD_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("OFFERPATH_RAG_EMBEDDER_MODE", "fake")
    get_settings.cache_clear()
    init_db()


def _create_user(db) -> User:
    user = User(email=f"rag-{uuid4().hex}@example.com", hashed_password="not-used")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _register_and_login(client: TestClient) -> str:
    email = f"rag-api-{uuid4().hex}@example.com"
    password = "strong-password"
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 201
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]
