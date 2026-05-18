from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Resume, User
from app.schemas import ResumeRead
from app.services.storage import save_resume_file

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Resume:
    stored_path = save_resume_file(file, current_user.id)
    resume = Resume(
        owner_id=current_user.id,
        original_filename=file.filename or "resume",
        stored_path=stored_path,
        content_type=file.content_type,
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
