import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["OFFERPATH_DATABASE_URL"] = "sqlite:///./test_offerpath.db"
os.environ["OFFERPATH_UPLOAD_DIR"] = "./test_storage/resumes"
Path("test_offerpath.db").unlink(missing_ok=True)

from app.db import SessionLocal, init_db
from app.main import app
from app.models import AnalysisJob, JobStatus, Resume, User
from worker.main import process_next_queued_job


def test_readiness_reports_database_and_optional_redis() -> None:
    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "ok"
    assert payload["redis"] in {"ok", "unavailable"}


def test_offerpath_async_worker_flow(tmp_path: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={"email": "max@example.com", "password": "strong-password"},
        )
        assert response.status_code == 201

        response = client.post(
            "/auth/login",
            data={"username": "max@example.com", "password": "strong-password"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resume = tmp_path / "resume.txt"
        resume.write_text("Python FastAPI SQL Docker testing", encoding="utf-8")
        with resume.open("rb") as file:
            response = client.post(
                "/resumes",
                headers=headers,
                files={"file": ("resume.txt", file, "text/plain")},
            )
        assert response.status_code == 201
        resume_id = response.json()["id"]

        response = client.post(
            "/jobs",
            headers=headers,
            json={
                "resume_id": resume_id,
                "target_title": "Backend Engineer",
                "job_description": "We need Python, FastAPI, PostgreSQL, Redis, AWS, SQS, S3, Docker, testing, and REST APIs.",
            },
        )
        assert response.status_code == 201
        job_id = response.json()["id"]
        assert response.json()["status"] == "queued"
        assert response.json()["attempt_count"] == 0
        assert response.json()["max_attempts"] == 3

        response = client.get(f"/jobs/{job_id}", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "queued"
        assert payload["result"] is None
        assert payload["started_at"] is None
        assert payload["finished_at"] is None

        db = SessionLocal()
        try:
            processed_job_id = process_next_queued_job(db)
            assert processed_job_id == job_id
        finally:
            db.close()

        response = client.get(f"/jobs/{job_id}", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "succeeded"
        assert payload["attempt_count"] == 1
        assert payload["started_at"] is not None
        assert payload["finished_at"] is not None
        assert payload["last_error"] is None
        assert "redis" in payload["result"]["missing_skills"]


def test_worker_processes_next_queued_job(tmp_path: Path) -> None:
    init_db()
    resume_file = tmp_path / "resume.txt"
    resume_file.write_text("Python FastAPI Docker testing", encoding="utf-8")

    db = SessionLocal()
    try:
        user = User(email="worker@example.com", hashed_password="not-used")
        db.add(user)
        db.commit()
        db.refresh(user)

        resume = Resume(
            owner_id=user.id,
            original_filename="resume.txt",
            stored_path=str(resume_file),
            content_type="text/plain",
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)

        job = AnalysisJob(
            owner_id=user.id,
            resume_id=resume.id,
            target_title="Backend Engineer",
            job_description="Python FastAPI PostgreSQL Redis AWS S3 SQS Docker testing REST APIs",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        processed_job_id = process_next_queued_job(db)

        db.refresh(job)
        assert processed_job_id == job.id
        assert job.status == JobStatus.succeeded
        assert job.attempt_count == 1
        assert job.started_at is not None
        assert job.finished_at is not None
        assert job.last_error is None
        assert job.result_json is not None
    finally:
        db.close()
