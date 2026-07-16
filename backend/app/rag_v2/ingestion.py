import hashlib
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import RAGChunk, RAGDocument, utc_now
from app.rag_v2.chunker import chunk_sections
from app.rag_v2.embedder import Embedder, create_embedder
from app.rag_v2.exceptions import RAGIngestionError, RAGParsingError
from app.rag_v2.parser import PARSER_VERSION, parse_pdf, parse_plain_text


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class RAGIngestionService:
    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or create_embedder()

    def create_document(
        self,
        db: Session,
        *,
        owner_id: int,
        source_type: str,
        title: str,
        content_bytes: bytes,
        storage_uri: str | None = None,
        metadata: dict | None = None,
    ) -> RAGDocument:
        content_hash = sha256_bytes(content_bytes)
        existing = db.scalar(
            select(RAGDocument).where(RAGDocument.owner_id == owner_id, RAGDocument.content_hash == content_hash)
        )
        if existing is not None:
            return existing
        document = RAGDocument(
            owner_id=owner_id,
            source_type=source_type,
            title=title,
            storage_uri=storage_uri,
            content_hash=content_hash,
            status="pending",
            metadata_json=metadata or {},
            parser_version=PARSER_VERSION,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    def ingest_text(
        self,
        db: Session,
        *,
        owner_id: int,
        source_type: str,
        title: str,
        text_content: str,
        metadata: dict | None = None,
    ) -> RAGDocument:
        content_bytes = text_content.encode("utf-8")
        document = self.create_document(
            db,
            owner_id=owner_id,
            source_type=source_type,
            title=title,
            content_bytes=content_bytes,
            storage_uri=None,
            metadata=metadata,
        )
        if document.status == "ready":
            return document
        return self._ingest_sections(db, document, parse_plain_text(text_content))

    def ingest_file(
        self,
        db: Session,
        *,
        owner_id: int,
        source_type: str,
        title: str,
        path: str | Path,
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> RAGDocument:
        file_path = Path(path)
        content_bytes = file_path.read_bytes()
        document = self.create_document(
            db,
            owner_id=owner_id,
            source_type=source_type,
            title=title,
            content_bytes=content_bytes,
            storage_uri=str(file_path),
            metadata={**(metadata or {}), "content_type": content_type},
        )
        if document.status == "ready":
            return document
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            sections = parse_pdf(file_path)
        elif suffix == ".txt":
            sections = parse_plain_text(content_bytes.decode("utf-8", errors="replace"))
        else:
            raise RAGIngestionError("Only PDF and TXT RAG uploads are supported")
        return self._ingest_sections(db, document, sections)

    def reingest_document(self, db: Session, *, owner_id: int, document_id: int) -> RAGDocument:
        document = self._owned_document(db, owner_id, document_id)
        if not document.storage_uri:
            raise RAGIngestionError("Text-only documents cannot be reingested without a storage URI")
        suffix = Path(document.storage_uri).suffix.lower()
        sections = parse_pdf(document.storage_uri) if suffix == ".pdf" else parse_plain_text(Path(document.storage_uri).read_text())
        return self._ingest_sections(db, document, sections)

    def delete_document(self, db: Session, *, owner_id: int, document_id: int) -> None:
        document = self._owned_document(db, owner_id, document_id)
        db.delete(document)
        db.commit()

    def _ingest_sections(self, db: Session, document: RAGDocument, sections) -> RAGDocument:
        try:
            document.status = "processing"
            document.error_message = None
            document.updated_at = utc_now()
            db.commit()
            chunks = chunk_sections(sections)
            if not chunks:
                raise RAGParsingError("No non-empty chunks were produced")
            embeddings = self.embedder.embed_documents([chunk.content for chunk in chunks])
            if len(embeddings) != len(chunks):
                raise RAGIngestionError("Embedding count did not match chunk count")
            with db.begin():
                db.execute(delete(RAGChunk).where(RAGChunk.document_id == document.id, RAGChunk.owner_id == document.owner_id))
                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    db.add(
                        RAGChunk(
                            document_id=document.id,
                            owner_id=document.owner_id,
                            chunk_index=chunk.chunk_index,
                            section_type=chunk.section_type,
                            heading=chunk.heading,
                            content=chunk.content,
                            estimated_token_count=chunk.estimated_token_count,
                            content_hash=chunk.content_hash,
                            metadata_json=chunk.metadata,
                            embedding=embedding,
                            embedding_model=get_settings().rag_embedding_model,
                            search_vector=chunk.content,
                        )
                    )
                document.status = "ready"
                document.updated_at = utc_now()
            _refresh_postgres_search_vectors(db, document.id)
            db.refresh(document)
            return document
        except Exception as exc:
            db.rollback()
            document.status = "failed"
            document.error_message = str(exc)[:1000]
            document.updated_at = utc_now()
            db.commit()
            raise

    def _owned_document(self, db: Session, owner_id: int, document_id: int) -> RAGDocument:
        document = db.scalar(select(RAGDocument).where(RAGDocument.id == document_id, RAGDocument.owner_id == owner_id))
        if document is None:
            raise RAGIngestionError("RAG document not found")
        return document


def _refresh_postgres_search_vectors(db: Session, document_id: int) -> None:
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    db.execute(
        text("UPDATE rag_chunks SET search_vector = to_tsvector('simple', coalesce(content, '')) WHERE document_id = :document_id"),
        {"document_id": document_id},
    )
    db.commit()
