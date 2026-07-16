import re
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


class StorageService(Protocol):
    backend_name: str

    def save_file(self, file_bytes: bytes, key: str, content_type: str | None = None) -> str:
        pass

    def read_file(self, key: str) -> bytes:
        pass

    def delete_file(self, key: str) -> None:
        pass

    def build_resume_key(self, user_id: int, original_filename: str) -> str:
        pass


class S3StorageService:
    backend_name = "s3"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.s3_bucket_name:
            raise RuntimeError("S3 storage requires S3_BUCKET_NAME")

        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("S3 storage requires boto3 to be installed") from exc

        client_kwargs = {}
        if settings.aws_region:
            client_kwargs["region_name"] = settings.aws_region
        # Local personal credentials are supported for development. In production,
        # prefer IAM roles on EC2/ECS and leave these unset.
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        self._bucket_name = settings.s3_bucket_name
        self._prefix = settings.s3_resume_prefix.strip("/") or "resumes"
        self._client = boto3.client("s3", **client_kwargs)
        self._error_types = (BotoCoreError, ClientError)

    def save_file(self, file_bytes: bytes, key: str, content_type: str | None = None) -> str:
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        try:
            self._client.put_object(
                Bucket=self._bucket_name,
                Key=key,
                Body=file_bytes,
                **({"ContentType": content_type} if content_type else {}),
            )
        except self._error_types as exc:
            raise RuntimeError(f"S3 upload failed for key {key}: {exc}") from exc
        return key

    def read_file(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket_name, Key=key)
            return response["Body"].read()
        except self._error_types as exc:
            raise RuntimeError(f"S3 read failed for key {key}: {exc}") from exc

    def delete_file(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket_name, Key=key)
        except self._error_types as exc:
            raise RuntimeError(f"S3 delete failed for key {key}: {exc}") from exc

    def build_resume_key(self, user_id: int, original_filename: str) -> str:
        safe_filename = sanitize_filename(original_filename or "resume")
        return f"{self._prefix}/user_{user_id}/{uuid4().hex}_{safe_filename}"


class LocalStorageService:
    backend_name = "local"

    def __init__(self) -> None:
        settings = get_settings()
        self._root = Path(settings.upload_dir)

    def save_file(self, file_bytes: bytes, key: str, content_type: str | None = None) -> str:
        target = self._root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_bytes)
        return str(target)

    def read_file(self, key: str) -> bytes:
        return Path(key).read_bytes()

    def delete_file(self, key: str) -> None:
        Path(key).unlink(missing_ok=True)

    def build_resume_key(self, user_id: int, original_filename: str) -> str:
        safe_filename = sanitize_filename(original_filename or "resume")
        return f"{user_id}/{uuid4().hex}_{safe_filename}"


def get_storage_service(backend_name: str | None = None) -> StorageService:
    settings = get_settings()
    backend = (backend_name or settings.storage_backend).lower()
    if backend == "s3":
        return S3StorageService()
    if backend == "local":
        return LocalStorageService()
    raise RuntimeError(f"Unsupported storage backend: {backend}")


def save_resume_file(upload: UploadFile, owner_id: int) -> str:
    file_bytes = upload.file.read()
    storage = get_storage_service()
    key = storage.build_resume_key(owner_id, upload.filename or "resume")
    return storage.save_file(file_bytes, key, upload.content_type)


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "resume"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)
