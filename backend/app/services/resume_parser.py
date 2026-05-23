from io import BytesIO
from pathlib import Path


def extract_resume_text(
    file_bytes: bytes,
    filename: str,
    content_type: str | None = None,
) -> str:
    suffix = Path(filename or "").suffix.lower()
    if _is_txt(suffix, content_type):
        return file_bytes.decode("utf-8", errors="ignore").strip()
    if _is_pdf(suffix, content_type):
        return _extract_pdf_text(file_bytes)
    raise ValueError("Unsupported resume format. Only PDF and TXT are supported")


def _is_txt(suffix: str, content_type: str | None) -> bool:
    return suffix == ".txt" or content_type == "text/plain"


def _is_pdf(suffix: str, content_type: str | None) -> bool:
    return suffix == ".pdf" or content_type == "application/pdf"


def _extract_pdf_text(file_bytes: bytes) -> str:
    if not file_bytes:
        raise ValueError("No extractable text found in PDF resume")

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("PDF resume parsing requires pypdf to be installed") from exc

    try:
        reader = PdfReader(BytesIO(file_bytes))
        page_text = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ValueError(f"PDF text extraction failed: {exc}") from exc

    text = "\n".join(part.strip() for part in page_text if part.strip()).strip()
    if not text:
        raise ValueError("No extractable text found in PDF resume")
    return text
