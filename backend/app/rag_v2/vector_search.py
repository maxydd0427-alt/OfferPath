import math

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import RAGChunk, RAGDocument
from app.rag_v2.schemas import RetrievalCandidate


def vector_search(
    db: Session,
    owner_id: int,
    query_embedding: list[float],
    limit: int,
    source_types: list[str] | None = None,
    document_ids: list[int] | None = None,
) -> list[RetrievalCandidate]:
    if not query_embedding or limit <= 0:
        return []
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return _postgres_vector_search(db, owner_id, query_embedding, limit, source_types, document_ids)
    return _python_vector_search(db, owner_id, query_embedding, limit, source_types, document_ids)


def _python_vector_search(db, owner_id, query_embedding, limit, source_types, document_ids):
    stmt = (
        select(RAGChunk, RAGDocument)
        .join(RAGDocument, RAGDocument.id == RAGChunk.document_id)
        .where(RAGChunk.owner_id == owner_id, RAGDocument.owner_id == owner_id, RAGDocument.status == "ready")
    )
    if source_types:
        stmt = stmt.where(RAGDocument.source_type.in_(source_types))
    if document_ids:
        stmt = stmt.where(RAGDocument.id.in_(document_ids))
    rows = db.execute(stmt).all()
    scored = []
    for chunk, document in rows:
        if chunk.embedding is None:
            continue
        score = _cosine(query_embedding, list(chunk.embedding))
        scored.append(_candidate(chunk, document, vector_score=score))
    return sorted(scored, key=lambda item: (-float(item.vector_score or 0), item.chunk_id))[:limit]


def _postgres_vector_search(db, owner_id, query_embedding, limit, source_types, document_ids):
    filters = ["c.owner_id = :owner_id", "d.owner_id = :owner_id", "d.status = 'ready'", "c.embedding IS NOT NULL"]
    params = {"owner_id": owner_id, "embedding": str(query_embedding), "limit": limit}
    if source_types:
        filters.append("d.source_type = ANY(:source_types)")
        params["source_types"] = source_types
    if document_ids:
        filters.append("d.id = ANY(:document_ids)")
        params["document_ids"] = document_ids
    sql = text(
        f"""
        SELECT c.id AS chunk_id, c.document_id, c.content, c.section_type, c.metadata_json,
               d.title, d.source_type, 1 - (c.embedding <=> CAST(:embedding AS vector)) AS vector_score
        FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id
        WHERE {' AND '.join(filters)}
        ORDER BY c.embedding <=> CAST(:embedding AS vector), c.id
        LIMIT :limit
        """
    )
    return [
        RetrievalCandidate(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            content=row.content,
            title=row.title,
            source_type=row.source_type,
            section_type=row.section_type,
            vector_score=float(row.vector_score),
            metadata=row.metadata_json or {},
        )
        for row in db.execute(sql, params)
    ]


def _cosine(left: list[float], right: list[float]) -> float:
    length = min(len(left), len(right))
    dot = sum(left[i] * right[i] for i in range(length))
    left_norm = math.sqrt(sum(value * value for value in left[:length])) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right[:length])) or 1.0
    return dot / (left_norm * right_norm)


def _candidate(chunk: RAGChunk, document: RAGDocument, *, vector_score: float | None = None, keyword_score: float | None = None) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk.id,
        document_id=document.id,
        content=chunk.content,
        title=document.title,
        source_type=document.source_type,
        section_type=chunk.section_type,
        vector_score=vector_score,
        keyword_score=keyword_score,
        metadata=chunk.metadata_json or {},
    )
