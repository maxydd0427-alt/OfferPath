import re
from pathlib import Path

from pypdf import PdfReader

from app.rag_v2.exceptions import RAGParsingError
from app.rag_v2.schemas import ParsedSection

PARSER_VERSION = "rag-parser-v2"

HEADING_TYPES = {
    "summary": "summary",
    "profile": "summary",
    "experience": "experience",
    "employment": "experience",
    "projects": "projects",
    "education": "education",
    "skills": "skills",
    "certifications": "certifications",
    "responsibilities": "responsibilities",
    "requirements": "requirements",
    "preferred qualifications": "requirements",
    "个人简介": "summary",
    "工作经历": "experience",
    "实习经历": "experience",
    "项目经历": "projects",
    "教育经历": "education",
    "技能": "skills",
    "证书": "certifications",
    "岗位职责": "responsibilities",
    "任职要求": "requirements",
}


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def classify_heading(line: str) -> str:
    key = re.sub(r"[:：\-\s]+$", "", line.strip()).lower()
    return HEADING_TYPES.get(key, "unknown")


def parse_pdf(path: str | Path) -> list[ParsedSection]:
    reader = PdfReader(str(path))
    sections: list[ParsedSection] = []
    for index, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or "")
        if text:
            sections.extend(_split_sections(text, page_number=index))
    if not sections:
        raise RAGParsingError("PDF has no extractable text; OCR is not supported")
    return sections


def parse_plain_text(text: str) -> list[ParsedSection]:
    normalized = normalize_text(text)
    if not normalized:
        raise RAGParsingError("Text document is empty")
    return _split_sections(normalized, page_number=None)


def _split_sections(text: str, page_number: int | None) -> list[ParsedSection]:
    lines = [line.strip() for line in text.splitlines()]
    current_heading: str | None = None
    current_type = "unknown"
    buffer: list[str] = []
    sections: list[ParsedSection] = []

    def flush() -> None:
        content = normalize_text("\n".join(buffer))
        if content:
            sections.append(
                ParsedSection(
                    heading=current_heading,
                    section_type=current_type,
                    text=content,
                    page_number=page_number,
                    metadata={"page_number": page_number, "parser_version": PARSER_VERSION},
                )
            )

    for line in lines:
        if not line:
            buffer.append("")
            continue
        section_type = classify_heading(line)
        looks_like_heading = section_type != "unknown" or line.endswith((":","："))
        if looks_like_heading and buffer:
            flush()
            buffer = []
        if looks_like_heading:
            current_heading = line
            current_type = section_type
            if section_type == "unknown":
                buffer.append(line)
            continue
        buffer.append(line)
    flush()
    return sections or [ParsedSection(text=text, page_number=page_number)]
