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


def test_extract_resume_text_reads_text_pdf() -> None:
    text = extract_resume_text(
        file_bytes=_minimal_text_pdf("Python FastAPI Redis"),
        filename="resume.pdf",
        content_type="application/pdf",
    )

    assert "Python FastAPI Redis" in text


def test_extract_resume_text_rejects_scanned_pdf_without_text() -> None:
    with pytest.raises(ValueError, match="No extractable text found in PDF resume"):
        extract_resume_text(
            file_bytes=_minimal_text_pdf(""),
            filename="resume.pdf",
            content_type="application/pdf",
        )


def _minimal_text_pdf(text: str) -> bytes:
    stream = f"BT /F1 24 Tf 100 700 Td ({text}) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream.encode('utf-8'))} >>\nstream\n{stream}\nendstream".encode("utf-8"),
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)
