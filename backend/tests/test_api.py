import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["OFFERPATH_DATABASE_URL"] = "sqlite:///./test_offerpath.db"
os.environ["OFFERPATH_UPLOAD_DIR"] = "./test_storage/resumes"
Path("test_offerpath.db").unlink(missing_ok=True)

from app.main import app


def test_offerpath_week_one_flow(tmp_path: Path) -> None:
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

        response = client.get(f"/jobs/{job_id}", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "succeeded"
        assert "redis" in payload["result"]["missing_skills"]
