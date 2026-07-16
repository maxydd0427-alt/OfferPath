import hashlib
import math
from typing import Protocol

try:
    from tenacity import retry, stop_after_attempt, wait_exponential
except ImportError:  # pragma: no cover - keeps existing local venvs testable
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def stop_after_attempt(*args, **kwargs):
        return None

    def wait_exponential(*args, **kwargs):
        return None

from app.core.config import get_settings
from app.rag_v2.exceptions import RAGConfigurationError


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, query: str) -> list[float]:
        ...


class FakeEmbedder:
    def __init__(self, dimension: int | None = None) -> None:
        self.dimension = dimension or get_settings().rag_embedding_dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._embed(query)

    def _embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [((digest[i % len(digest)] / 255.0) * 2.0) - 1.0 for i in range(self.dimension)]
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


class GeminiEmbedder:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RAGConfigurationError("missing API key: set OFFERPATH_GEMINI_API_KEY for Gemini embeddings")
        self.api_key = settings.gemini_api_key
        self.model = settings.rag_embedding_model
        self.dimension = settings.rag_embedding_dimension
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise RAGConfigurationError("google-genai is required for Gemini embeddings") from exc
        self.client = genai.Client(api_key=self.api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, query: str) -> list[float]:
        return self._embed([query], task_type="RETRIEVAL_QUERY")[0]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.models.embed_content(
            model=self.model,
            contents=texts,
            config={"task_type": task_type, "output_dimensionality": self.dimension},
        )
        embeddings = [list(item.values) for item in response.embeddings]
        if len(embeddings) != len(texts):
            raise RAGConfigurationError("Gemini embedding response count did not match input count")
        for vector in embeddings:
            if len(vector) != self.dimension:
                raise RAGConfigurationError("Gemini embedding dimension did not match configuration")
        return embeddings


def create_embedder() -> Embedder:
    settings = get_settings()
    mode = settings.rag_embedder_mode.lower()
    if mode == "fake" or settings.env.lower() in {"test", "ci"}:
        return FakeEmbedder()
    if mode == "gemini" or settings.gemini_api_key:
        return GeminiEmbedder()
    return FakeEmbedder()
