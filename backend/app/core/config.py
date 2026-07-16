from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OfferPath"
    env: str = "local"
    database_url: str = "sqlite:///./offerpath.db"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    upload_dir: str = "./storage/resumes"
    redis_url: str = "redis://localhost:6379/0"
    analysis_workflow: str = Field(
        default="provider",
        validation_alias=AliasChoices("OFFERPATH_ANALYSIS_WORKFLOW", "ANALYSIS_WORKFLOW"),
    )
    ai_provider: str = "mock"
    agent_planner: str = Field(
        default="heuristic",
        validation_alias=AliasChoices("OFFERPATH_AGENT_PLANNER", "AGENT_PLANNER"),
    )
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash-lite"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174"
    storage_backend: str = Field(
        default="s3",
        validation_alias=AliasChoices("OFFERPATH_STORAGE_BACKEND", "STORAGE_BACKEND"),
    )
    aws_region: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OFFERPATH_AWS_REGION", "AWS_REGION"),
    )
    s3_bucket_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OFFERPATH_S3_BUCKET_NAME", "S3_BUCKET_NAME"),
    )
    s3_resume_prefix: str = Field(
        default="resumes",
        validation_alias=AliasChoices("OFFERPATH_S3_RESUME_PREFIX", "S3_RESUME_PREFIX"),
    )
    rag_v2_enabled: bool = True
    rag_embedding_model: str = "gemini-embedding-001"
    rag_embedding_dimension: int = 768
    rag_embedder_mode: str = Field(default="auto", validation_alias=AliasChoices("OFFERPATH_RAG_EMBEDDER_MODE", "RAG_EMBEDDER_MODE"))
    rag_chunk_size_chars: int = 1400
    rag_chunk_overlap_chars: int = 180
    rag_minimum_chunk_chars: int = 120
    rag_vector_limit: int = 20
    rag_keyword_limit: int = 20
    rag_hybrid_limit: int = 15
    rag_final_limit: int = 6
    rag_rrf_k: int = 60
    rag_max_context_chars: int = 12000
    rag_pipeline_version: str = "rag-v2"
    rag_reranker_enabled: bool = True
    rag_upload_max_bytes: int = 10485760
    aws_access_key_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OFFERPATH_AWS_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID"),
    )
    aws_secret_access_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OFFERPATH_AWS_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY"),
    )
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OFFERPATH_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_database_backend(database_url: str) -> str:
    if database_url.startswith("sqlite"):
        return "sqlite"
    if database_url.startswith(("postgresql", "postgres")):
        return "postgresql"
    return "unknown"
