# OfferPath

OfferPath is an agentic career growth backend that turns a resume and a target job description into a structured skill gap analysis, 30-day roadmap, proof-oriented project tasks, and interview preparation plan.

The long-term product goal is not only to generate advice. OfferPath should help a user repeatedly improve toward a target role by combining:

- resume and JD analysis
- long-term personal career context
- RAG over resumes, JDs, notes, projects, and interview records
- ReAct-style career agent orchestration for market JD search, GitHub references, Notion notes, and Gmail drafts

## Product Direction

The core idea is:

```text
Resume + Target JD
-> structured skill gap analysis
-> roadmap
-> user feedback revision
-> similar JD / market signal retrieval
-> GitHub reference projects
-> Notion learning notes
-> Gmail progress drafts
-> iterative improvement
```

For roles such as AI SRE, backend engineer, cloud engineer, and AI agent engineer, OfferPath should answer:

- Which skills does this role require?
- Which skills does the resume already prove?
- Which skills are missing or weak?
- What should the user learn in the next 30 days?
- What project can prove those skills?
- What do similar JDs ask for in the market?
- Which GitHub projects are useful references?
- What should be saved as learning notes?
- What progress update or outreach email should be drafted?

## Current Architecture

The stable backend path is still provider-based:

```text
FastAPI
-> AnalysisJob
-> worker
-> AnalysisProvider
-> AnalysisResult
-> result_json / intermediate_json
```

This path is intentionally boring and reliable. It supports:

- user registration and login
- PDF/TXT resume upload
- target JD submission
- async job creation
- worker processing
- mock provider for local tests
- Gemini provider for real AI output
- structured Pydantic validation before saving results
- Redis-backed rate limiting, idempotency, live status, and worker locks

The production API does not depend on experimental agent code by default.

## ReAct Career Agent

The main career agent now lives under:

```text
backend/app/services/career_agent/
```

The key entrypoint is:

```python
run_career_agent_preview(db, job_id, user_feedback=None)
```

This preview demonstrates a bounded ReAct loop:

```text
Reason -> Act -> Observation -> ... -> validated final output
```

The ReAct agent is the intended iterative product flow. It can:

- read the resume and target JD
- reuse previous successful analysis context
- use external market/JD/GitHub observations inside the reasoning loop
- generate and validate the structured roadmap
- revise the roadmap from user feedback
- search GitHub reference projects for roadmap tasks
- draft a Notion learning note
- draft a Gmail progress update
- keep all writes draft-only unless the user explicitly confirms

Current agent structure:

```text
career_agent/
  __init__.py
  tools.py              # safe internal tools for resume/JD/history
  result_builder.py     # builds and validates AnalysisResult
  mcp_adapters.py       # GitHub/Notion/Gmail adapter boundary
  career_agent.py       # ReAct orchestration loop
```

The MCP adapter is currently deterministic and safe for tests. It does not call real GitHub, Notion, or Gmail yet. The boundary is ready for real MCP connectors later:

```text
github_mcp_search_reference_projects
notion_mcp_draft_learning_note
gmail_mcp_draft_progress_update
```

Safety rules:

- GitHub is read/search oriented.
- Notion is draft-only by default.
- Gmail is draft-only by default.
- No unrestricted database access is exposed to the agent.
- No external publish/send should happen without explicit user confirmation.

MCP and retrieval outputs are observations inside the ReAct loop, not just
post-processing. They can shape the roadmap before the final validated result
is returned.

## RAG Plan

OfferPath should use **Amazon Bedrock Managed Knowledge Base** as the RAG layer.

The first RAG version should not use pgvector. Bedrock KB is the better MVP choice because it is fully managed and lets the project focus on retrieval strategy, multi-tenant filtering, and context orchestration.

Target RAG sources:

- multiple resumes
- historical JDs
- project notes
- interview notes
- learning notes
- company/job-role documents
- useful technical references

Planned Bedrock KB design:

```text
S3 documents
-> Bedrock Managed Knowledge Base
-> metadata-filtered retrieval
-> retrieved context
-> ReAct career agent / AnalysisProvider
```

Important production details:

- Add `user_id` metadata to documents/chunks.
- Always filter retrieval by `user_id`.
- Enable hybrid search where the Bedrock KB vector store supports it.
- Report retrieval latency and error metrics to CloudWatch.

Example retrieval filter:

```python
retrievalConfiguration={
    "vectorSearchConfiguration": {
        "numberOfResults": 5,
        "overrideSearchType": "HYBRID",
        "filter": {
            "equals": {
                "key": "user_id",
                "value": str(user_id),
            }
        },
    }
}
```

This lets OfferPath tell a stronger architecture story:

```text
multi-tenant isolated RAG
hybrid retrieval
observable retrieval latency
agentic tool orchestration
structured output validation
```

## Backend Stack

- FastAPI
- SQLAlchemy
- SQLite locally, PostgreSQL in Docker/AWS
- Redis
- S3-compatible resume storage boundary
- Gemini provider
- Mock provider for tests
- Bedrock KB planned for RAG
- ReAct career agent adapter boundary for GitHub, Notion, and Gmail

## Local Setup

Create the backend environment:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Start Redis:

```bash
docker compose up redis
```

Start the API:

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

Run the worker once:

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. python -m worker.main --once
```

Run tests:

```bash
cd backend
source .venv/bin/activate
pytest
```

## Demo Flow

1. `POST /auth/register`
2. `POST /auth/login`
3. Authorize Swagger with `Bearer <access_token>`
4. `POST /resumes` with a text-based PDF or TXT resume
5. `POST /jobs` with a target JD
6. Run the worker
7. `GET /jobs/{job_id}`

Example AI SRE job body:

```json
{
  "resume_id": 1,
  "target_title": "AI SRE",
  "job_description": "We need an AI SRE who can run production AI systems on AWS, build observability dashboards, debug incidents, operate Kubernetes workloads, design async queues, understand LLM workflows, write Python services, manage Redis/PostgreSQL, automate CI/CD, and explain reliability trade-offs."
}
```

Successful jobs return a structured result with:

- `matched_skills`
- prioritized `missing_skills`
- `weak_skills`
- `partially_matched_skills`
- `evidence_from_resume`
- `evidence_from_jd`
- `30_day_roadmap`
- `project_tasks`
- `interview_talking_points`
- `resume_improvement_suggestions`

## Configuration

Local secrets belong in:

```text
backend/.env
```

Do not commit `.env`.

AI provider:

```env
OFFERPATH_AI_PROVIDER=mock
OFFERPATH_GEMINI_MODEL=gemini-2.5-flash
# OFFERPATH_GEMINI_API_KEY=your-local-secret
```

Switch to Gemini:

```env
OFFERPATH_AI_PROVIDER=gemini
OFFERPATH_GEMINI_API_KEY=your-local-secret
```

Storage:

```env
STORAGE_BACKEND=local
OFFERPATH_UPLOAD_DIR=./storage/resumes
```

Future Bedrock KB RAG:

```env
OFFERPATH_RAG_PROVIDER=bedrock_kb
OFFERPATH_BEDROCK_KB_ID=your-kb-id
OFFERPATH_BEDROCK_MODEL_ARN=your-model-arn
OFFERPATH_AWS_REGION=ap-southeast-2
OFFERPATH_RAG_SEARCH_TYPE=HYBRID
OFFERPATH_RAG_NUMBER_OF_RESULTS=5
```

## Reliability Features

Redis is used for:

- rate limiting
- idempotency keys
- live job status
- worker locks

The database remains the source of truth for:

- users
- resumes
- jobs
- results
- intermediate steps

## Project Principle

OfferPath should not only help users look stronger on paper.

It should help them become stronger in reality by turning career gaps into concrete learning tasks, proof projects, reference examples, and follow-up actions.
