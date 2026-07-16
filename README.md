# OfferPath

OfferPath is an AI career-development app for computer science students and software job seekers. It turns a resume and target job description into a structured skill gap analysis, a 30-day roadmap, proof-oriented project tasks, interview preparation, and evidence-backed recommendations.

## Product Flow

```text
Resume PDF/TXT + Target Job Description
-> AnalysisJob
-> worker
-> optional RAG V2 evidence retrieval
-> AnalysisProvider or career agent
-> Pydantic validated AnalysisResult
-> result_json + intermediate_json
```

The backend is FastAPI-based and includes auth, resume upload, async jobs, Redis-backed idempotency/status/locks, PostgreSQL or SQLite support, and mock/Gemini/OpenAI analysis providers. The React frontend demo calls the real FastAPI endpoints and includes a local demo-result fallback for presentation.

## Frontend Demo

```bash
cd frontend
npm install
npm run dev
```

The API defaults to `http://localhost:8000`. Override it with:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

The frontend uses real routes for auth, resume upload, job creation, polling, live status, and result rendering. Demo mode uses local mock data only.

## Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For local SQLite development:

```bash
cd backend
OFFERPATH_STORAGE_BACKEND=local OFFERPATH_AI_PROVIDER=mock .venv/bin/uvicorn app.main:app --reload --port 8000
```

For Docker dependencies:

```bash
docker compose up -d postgres redis
cd backend
alembic upgrade head
```

Start API and worker:

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
cd backend
.venv/bin/python -m worker.main --poll-interval-seconds 5
```

## RAG V2 Architecture

OfferPath RAG V2 lives under `backend/app/rag_v2/`.

Implemented functionality:

- PostgreSQL + pgvector storage for embeddings
- PostgreSQL full-text search with `websearch_to_tsquery` and `ts_rank_cd`
- Reciprocal Rank Fusion for hybrid vector/keyword retrieval
- Gemini embeddings with deterministic `FakeEmbedder` fallback
- LLM reranking with deterministic score-only fallback
- Tenant-isolated retrieval using `owner_id` filters at query time
- Evidence citations (`C1`, `C2`, `C3`, ...)
- Retrieval traces in `rag_runs`
- Offline Recall@K, MRR, empty retrieval, latency, and tenant-isolation evaluation

The bundled evaluation corpus contains controlled synthetic and user-authored demo data.

### RAG V2 Flow

```text
Document text or PDF
-> parser
-> section-aware chunker
-> Gemini or fake embeddings
-> rag_documents / rag_chunks
-> vector search + full-text search
-> Reciprocal Rank Fusion
-> reranker with fallback
-> bounded evidence context with citations
-> analysis provider prompt
-> intermediate_json["rag_v2"]
```

### RAG V2 Environment

Defaults are shown below:

```bash
OFFERPATH_RAG_V2_ENABLED=true
OFFERPATH_RAG_EMBEDDING_MODEL=gemini-embedding-001
OFFERPATH_RAG_EMBEDDING_DIMENSION=768
OFFERPATH_RAG_EMBEDDER_MODE=auto
OFFERPATH_RAG_CHUNK_SIZE_CHARS=1400
OFFERPATH_RAG_CHUNK_OVERLAP_CHARS=180
OFFERPATH_RAG_MINIMUM_CHUNK_CHARS=120
OFFERPATH_RAG_VECTOR_LIMIT=20
OFFERPATH_RAG_KEYWORD_LIMIT=20
OFFERPATH_RAG_HYBRID_LIMIT=15
OFFERPATH_RAG_FINAL_LIMIT=6
OFFERPATH_RAG_RRF_K=60
OFFERPATH_RAG_MAX_CONTEXT_CHARS=12000
OFFERPATH_RAG_PIPELINE_VERSION=rag-v2
OFFERPATH_RAG_RERANKER_ENABLED=true
OFFERPATH_RAG_UPLOAD_MAX_BYTES=10485760
```

Use `OFFERPATH_RAG_EMBEDDER_MODE=fake` for deterministic local development without Gemini credentials. Production Gemini embedding requires `OFFERPATH_GEMINI_API_KEY`; do not commit `.env`.

### RAG API

Authenticated routes:

- `POST /rag/documents/text`
- `POST /rag/documents/upload`
- `GET /rag/documents`
- `GET /rag/documents/{id}`
- `DELETE /rag/documents/{id}`
- `POST /rag/documents/{id}/reingest`
- `POST /rag/search`

Owner IDs come from the authenticated user. Callers cannot impersonate another user.

### Seed Demo Corpus

```bash
cd backend
OFFERPATH_RAG_EMBEDDER_MODE=fake .venv/bin/python scripts/seed_rag_demo.py
```

The seed script is idempotent by content hash.

### Offline Evaluation

```bash
cd backend
OFFERPATH_RAG_EMBEDDER_MODE=fake .venv/bin/python scripts/evaluate_rag.py
```

Optional JSON output:

```bash
OFFERPATH_RAG_EMBEDDER_MODE=fake .venv/bin/python scripts/evaluate_rag.py --json
```

The script reports actual Recall@1, Recall@3, Recall@5, MRR, Empty Retrieval Rate, Tenant Isolation Pass Rate, and Average Retrieval Latency. It does not hard-code success numbers.

## Analysis Providers

Local deterministic tests:

```bash
OFFERPATH_AI_PROVIDER=mock
```

Gemini:

```bash
OFFERPATH_AI_PROVIDER=gemini
OFFERPATH_GEMINI_MODEL=gemini-2.0-flash-lite
OFFERPATH_GEMINI_API_KEY=your-local-secret
```

OpenAI:

```bash
OFFERPATH_AI_PROVIDER=openai
OFFERPATH_OPENAI_MODEL=gpt-4o-mini
OFFERPATH_OPENAI_API_KEY=your-local-secret
```

API keys belong in `backend/.env`. `.env.example` must contain placeholders only.

## Career Agent

The bounded ReAct-style career agent lives under `backend/app/services/career_agent/`. It can read the resume/JD, reuse previous successful analysis context, revise a roadmap from user feedback, search GitHub reference projects through the MCP adapter, and draft Notion/Gmail outputs without publishing or sending by default.

RAG V2 is integrated into the provider worker path. The career-agent MCP path is kept focused on agent actions and external-tool drafts.

## Tests

Run backend tests with a clean temporary SQLite database:

```bash
cd backend
OFFERPATH_DATABASE_URL=sqlite:////private/tmp/offerpath-test.db \
OFFERPATH_ENV=test \
OFFERPATH_RAG_EMBEDDER_MODE=fake \
.venv/bin/python -m pytest
```

Run frontend build:

```bash
cd frontend
npm run build
```

## Manual Swagger Check

1. Start API, open `http://localhost:8000/docs`, register/login, and authorize with the bearer token.
2. Create a RAG text document through `POST /rag/documents/text`.
3. Query `POST /rag/search` and confirm citations are returned.
4. Upload a resume, create an analysis job, and run it.
5. Confirm `GET /jobs/{id}` includes `intermediate_steps.rag_v2` and that another user cannot access the first user’s RAG document.
