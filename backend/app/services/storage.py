from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


def save_resume_file(upload: UploadFile, owner_id: int) -> str:
    settings = get_settings()
    upload_dir = Path(settings.upload_dir) / str(owner_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(upload.filename or "resume").suffix
    target = upload_dir / f"{uuid4().hex}{suffix}"
    with target.open("wb") as destination:
        while chunk := upload.file.read(1024 * 1024):
            destination.write(chunk)
    return str(target)
