import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db import get_db
from app.models import RAGDocument, User
from app.rag_v2 import OfferPathRetriever, RAGIngestionService
from app.rag_v2.exceptions import RAGIngestionError, RAGParsingError

router = APIRouter(prefix="/rag", tags=["rag"])

ALLOWED_SOURCE_TYPES = {"resume", "job_description", "project_note", "interview_note", "career_knowledge"}
ALLOWED_SUFFIXES = {".pdf", ".txt"}
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain", "application/octet-stream"}


class RAGTextCreate(BaseModel):
    source_type: str = Field(pattern="^(resume|job_description|project_note|interview_note|career_knowledge)$")
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGDocumentRead(BaseModel):
    id: int
    source_type: str
    title: str
    storage_uri: str | None
    content_hash: str
    status: str
    metadata_json: dict[str, Any]
    parser_version: str
    error_message: str | None

    model_config = {"from_attributes": True}


class RAGSearchRequest(BaseModel):
    target_title: str = Field(min_length=1, max_length=120)
    job_description: str = Field(min_length=1)
    source_types: list[str] | None = None


@router.post("/documents/text", response_model=RAGDocumentRead, status_code=status.HTTP_201_CREATED)
def create_text_document(
    payload: RAGTextCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RAGDocument:
    try:
        return RAGIngestionService().ingest_text(
            db,
            owner_id=current_user.id,
            source_type=payload.source_type,
            title=payload.title,
            text_content=payload.text,
            metadata=payload.metadata,
        )
    except (RAGIngestionError, RAGParsingError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/upload", response_model=RAGDocumentRead, status_code=status.HTTP_201_CREATED)
def upload_document(
    source_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RAGDocument:
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported source_type")
    filename = file.filename or "document"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES or file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="RAG upload must be a PDF or TXT file")
    file_bytes = file.file.read()
    settings = get_settings()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="RAG upload is empty")
    if len(file_bytes) > settings.rag_upload_max_bytes:
        raise HTTPException(status_code=413, detail="RAG upload exceeds configured size limit")
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)
        return RAGIngestionService().ingest_file(
            db,
            owner_id=current_user.id,
            source_type=source_type,
            title=filename,
            path=tmp_path,
            content_type=file.content_type,
            metadata={"filename": filename},
        )
    except (RAGIngestionError, RAGParsingError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/documents", response_model=list[RAGDocumentRead])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RAGDocument]:
    return list(db.scalars(select(RAGDocument).where(RAGDocument.owner_id == current_user.id).order_by(RAGDocument.id.desc())))


@router.get("/documents/{document_id}", response_model=RAGDocumentRead)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RAGDocument:
    document = db.scalar(select(RAGDocument).where(RAGDocument.id == document_id, RAGDocument.owner_id == current_user.id))
    if document is None:
        raise HTTPException(status_code=404, detail="RAG document not found")
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        RAGIngestionService().delete_document(db, owner_id=current_user.id, document_id=document_id)
    except RAGIngestionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/documents/{document_id}/reingest", response_model=RAGDocumentRead)
def reingest_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RAGDocument:
    try:
        return RAGIngestionService().reingest_document(db, owner_id=current_user.id, document_id=document_id)
    except (RAGIngestionError, RAGParsingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/search")
def search(
    payload: RAGSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    result = OfferPathRetriever().retrieve_for_analysis(
        db,
        owner_id=current_user.id,
        analysis_job_id=None,
        target_title=payload.target_title,
        job_description=payload.job_description,
        source_types=payload.source_types,
    )
    return result.model_dump()
