import hashlib
import re

from app.core.config import get_settings
from app.rag_v2.schemas import ChunkInput, ParsedSection


def normalized_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def chunk_sections(sections: list[ParsedSection]) -> list[ChunkInput]:
    settings = get_settings()
    chunks: list[ChunkInput] = []
    seen: set[str] = set()
    for section in sections:
        for content in _chunk_text(section.text, settings.rag_chunk_size_chars, settings.rag_chunk_overlap_chars):
            if len(content) < settings.rag_minimum_chunk_chars and chunks:
                previous = chunks[-1]
                merged = f"{previous.content}\n\n{content}".strip()
                chunks[-1] = previous.model_copy(
                    update={
                        "content": merged,
                        "estimated_token_count": max(1, len(merged) // 4),
                        "content_hash": normalized_hash(merged),
                    }
                )
                continue
            content_hash = normalized_hash(content)
            if not content or content_hash in seen:
                continue
            seen.add(content_hash)
            chunks.append(
                ChunkInput(
                    chunk_index=len(chunks),
                    section_type=section.section_type,
                    heading=section.heading,
                    content=content,
                    estimated_token_count=max(1, len(content) // 4),
                    content_hash=content_hash,
                    metadata={**section.metadata, "page_number": section.page_number},
                )
            )
    return chunks


def _chunk_text(text: str, size: int, overlap: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n|^\s*[-*•]\s+", text, flags=re.MULTILINE) if part.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > size:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_sliding_chunks(paragraph, size, overlap))
            continue
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= size:
            current = candidate
        else:
            chunks.append(current.strip())
            current = _with_overlap(current, overlap, paragraph)
    if current.strip():
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk.strip()]


def _sliding_chunks(text: str, size: int, overlap: int) -> list[str]:
    output: list[str] = []
    step = max(1, size - overlap)
    for start in range(0, len(text), step):
        chunk = text[start : start + size].strip()
        if chunk:
            output.append(chunk)
        if start + size >= len(text):
            break
    return output


def _with_overlap(previous: str, overlap: int, next_paragraph: str) -> str:
    tail = previous[-overlap:].strip() if overlap > 0 else ""
    return f"{tail}\n\n{next_paragraph}".strip()
