from typing import Any

from pydantic import BaseModel, Field


class ParsedSection(BaseModel):
    heading: str | None = None
    section_type: str = "unknown"
    text: str
    page_number: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkInput(BaseModel):
    chunk_index: int
    section_type: str = "unknown"
    heading: str | None = None
    content: str
    estimated_token_count: int
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalCandidate(BaseModel):
    chunk_id: int
    document_id: int
    content: str
    title: str
    source_type: str
    section_type: str
    vector_score: float | None = None
    keyword_score: float | None = None
    hybrid_score: float | None = None
    rerank_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    citation_id: str
    chunk_id: int
    document_id: int
    title: str
    source_type: str
    section_type: str
    evidence_text: str
    score: float


class RetrievalResult(BaseModel):
    query: str
    rewritten_queries: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    context: str = ""
    retrieved_chunk_ids: list[int] = Field(default_factory=list)
    selected_chunk_ids: list[int] = Field(default_factory=list)
    latency_ms: int = 0
    status: str = "succeeded"
    error_message: str | None = None
    pipeline_version: str
