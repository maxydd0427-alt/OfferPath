from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Resume, User
from app.schemas import ResumeRead
from app.services.storage import get_storage_service

router = APIRouter(prefix="/resumes", tags=["resumes"])

ALLOWED_RESUME_SUFFIXES = {".pdf", ".txt"}
MAX_RESUME_BYTES = 10 * 1024 * 1024


@router.post("", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Resume:
    original_filename = file.filename or "resume"
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_RESUME_SUFFIXES:
        raise HTTPException(status_code=400, detail="Resume must be a PDF or TXT file")

    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Resume file is empty")
    if len(file_bytes) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Resume file must be 10MB or smaller")

    storage = get_storage_service()
    storage_key = storage.build_resume_key(current_user.id, original_filename)
    try:
        stored_path = storage.save_file(file_bytes, storage_key, file.content_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    resume = Resume(
        owner_id=current_user.id,
        original_filename=original_filename,
        stored_path=stored_path,
        storage_backend=storage.backend_name,
        content_type=file.content_type,
        file_size=len(file_bytes),
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeRead])
def list_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Resume]:
    return list(db.scalars(select(Resume).where(Resume.owner_id == current_user.id)))
