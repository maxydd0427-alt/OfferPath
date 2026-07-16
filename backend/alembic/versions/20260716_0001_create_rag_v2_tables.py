"""create rag v2 tables

Revision ID: 20260716_0001
Revises:
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover
    Vector = None  # type: ignore[assignment]

revision = "20260716_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    embedding_type = Vector(768) if is_postgres and Vector is not None else sa.JSON()
    search_vector_type = postgresql.TSVECTOR() if is_postgres else sa.Text()
    json_type = postgresql.JSONB() if is_postgres else sa.JSON()

    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("storage_uri", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("metadata_json", json_type, nullable=False, server_default=sa.text("'{}'::jsonb") if is_postgres else None),
        sa.Column("parser_version", sa.String(), nullable=False, server_default="rag-parser-v2"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('resume', 'job_description', 'project_note', 'interview_note', 'career_knowledge')",
            name="ck_rag_documents_source_type",
        ),
        sa.CheckConstraint("status IN ('pending', 'processing', 'ready', 'failed')", name="ck_rag_documents_status"),
        sa.UniqueConstraint("owner_id", "content_hash", name="uq_rag_documents_owner_content_hash"),
    )
    op.create_index("ix_rag_documents_owner_status", "rag_documents", ["owner_id", "status"])
    op.create_index("ix_rag_documents_owner_source_type", "rag_documents", ["owner_id", "source_type"])
    if is_postgres:
        op.create_index("ix_rag_documents_metadata", "rag_documents", ["metadata_json"], postgresql_using="gin")

    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section_type", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("heading", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("estimated_token_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False, server_default=sa.text("'{}'::jsonb") if is_postgres else None),
        sa.Column("embedding", embedding_type, nullable=True),
        sa.Column("embedding_model", sa.String(), nullable=True),
        sa.Column("search_vector", search_vector_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "content_hash", name="uq_rag_chunks_document_content_hash"),
    )
    op.create_index("ix_rag_chunks_owner_document", "rag_chunks", ["owner_id", "document_id"])
    op.create_index("ix_rag_chunks_owner_section", "rag_chunks", ["owner_id", "section_type"])
    if is_postgres:
        op.execute("UPDATE rag_chunks SET search_vector = to_tsvector('simple', coalesce(content, ''))")
        op.create_index("ix_rag_chunks_search_vector", "rag_chunks", ["search_vector"], postgresql_using="gin")
        op.create_index("ix_rag_chunks_metadata", "rag_chunks", ["metadata_json"], postgresql_using="gin")
        op.execute("CREATE INDEX ix_rag_chunks_embedding_hnsw ON rag_chunks USING hnsw (embedding vector_cosine_ops)")

    op.create_table(
        "rag_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_job_id", sa.Integer(), sa.ForeignKey("analysis_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("rewritten_queries", json_type, nullable=False, server_default=sa.text("'[]'::jsonb") if is_postgres else None),
        sa.Column("retrieved_chunk_ids", json_type, nullable=False, server_default=sa.text("'[]'::jsonb") if is_postgres else None),
        sa.Column("selected_chunk_ids", json_type, nullable=False, server_default=sa.text("'[]'::jsonb") if is_postgres else None),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retrieved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="succeeded"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("pipeline_version", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rag_runs_owner_job", "rag_runs", ["owner_id", "analysis_job_id"])
    op.create_index("ix_rag_runs_owner_created", "rag_runs", ["owner_id", "created_at"])


def downgrade() -> None:
    op.drop_table("rag_runs")
    op.drop_table("rag_chunks")
    op.drop_table("rag_documents")
