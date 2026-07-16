import re

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import RAGChunk, RAGDocument
from app.rag_v2.schemas import RetrievalCandidate
from app.rag_v2.vector_search import _candidate


def keyword_search(
    db: Session,
    owner_id: int,
    query: str,
    limit: int,
    source_types: list[str] | None = None,
    document_ids: list[int] | None = None,
) -> list[RetrievalCandidate]:
    query = query.strip()
    if not query or limit <= 0:
        return []
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return _postgres_keyword_search(db, owner_id, query, limit, source_types, document_ids)
    return _python_keyword_search(db, owner_id, query, limit, source_types, document_ids)


def _python_keyword_search(db, owner_id, query, limit, source_types, document_ids):
    terms = [term.lower() for term in re.findall(r"[\w+#.-]+", query) if len(term) > 1]
    if not terms:
        return []
    stmt = (
        select(RAGChunk, RAGDocument)
        .join(RAGDocument, RAGDocument.id == RAGChunk.document_id)
        .where(RAGChunk.owner_id == owner_id, RAGDocument.owner_id == owner_id, RAGDocument.status == "ready")
    )
    if source_types:
        stmt = stmt.where(RAGDocument.source_type.in_(source_types))
    if document_ids:
        stmt = stmt.where(RAGDocument.id.in_(document_ids))
    scored = []
    for chunk, document in db.execute(stmt).all():
        content = chunk.content.lower()
        score = sum(content.count(term) for term in terms)
        if score:
            scored.append(_candidate(chunk, document, keyword_score=float(score)))
    return sorted(scored, key=lambda item: (-float(item.keyword_score or 0), item.chunk_id))[:limit]


def _postgres_keyword_search(db, owner_id, query, limit, source_types, document_ids):
    filters = ["c.owner_id = :owner_id", "d.owner_id = :owner_id", "d.status = 'ready'"]
    params = {"owner_id": owner_id, "query": query, "limit": limit}
    if source_types:
        filters.append("d.source_type = ANY(:source_types)")
        params["source_types"] = source_types
    if document_ids:
        filters.append("d.id = ANY(:document_ids)")
        params["document_ids"] = document_ids
    sql = text(
        f"""
        WITH q AS (SELECT websearch_to_tsquery('simple', :query) AS tsq)
        SELECT c.id AS chunk_id, c.document_id, c.content, c.section_type, c.metadata_json,
               d.title, d.source_type, ts_rank_cd(c.search_vector, q.tsq) AS keyword_score
        FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id, q
        WHERE {' AND '.join(filters)} AND c.search_vector @@ q.tsq
        ORDER BY keyword_score DESC, c.id
        LIMIT :limit
        """
    )
    try:
        rows = db.execute(sql, params)
    except Exception:
        return []
    return [
        RetrievalCandidate(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            content=row.content,
            title=row.title,
            source_type=row.source_type,
            section_type=row.section_type,
            keyword_score=float(row.keyword_score),
            metadata=row.metadata_json or {},
        )
        for row in rows
    ]
