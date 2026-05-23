import pytest

from app.services.resume_parser import extract_resume_text


def test_extract_resume_text_reads_txt_bytes() -> None:
    text = extract_resume_text(
        file_bytes="Python FastAPI Redis".encode("utf-8"),
        filename="resume.txt",
        content_type="text/plain",
    )

    assert text == "Python FastAPI Redis"


def test_extract_resume_text_rejects_empty_pdf() -> None:
    with pytest.raises(ValueError, match="No extractable text found in PDF resume"):
        extract_resume_text(
            file_bytes=b"",
            filename="resume.pdf",
            content_type="application/pdf",
        )
