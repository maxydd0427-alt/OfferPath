# OfferPath

**OfferPath** is an agentic career growth platform that helps users turn resumes and job descriptions into an actionable roadmap.

It does not just rewrite resumes or generate generic advice. Instead, it analyzes the gap between a candidate’s current skills and a target role, then produces a structured improvement plan, recommended project directions, and interview preparation tasks.

The system is designed as a real backend engineering project with async job processing, queue-based task execution, cloud deployment, and AI-powered decision workflows.

---

## 1. Why this project exists

In the AI era, many people can make their resumes look polished, but their real skill level may not match what the resume suggests.

At the same time, most job descriptions are not useful by themselves unless someone can answer these questions:

- What skills does this role actually require?
- Which of those skills do I already have?
- What am I missing?
- What should I learn first?
- What kind of project can prove those skills?
- What interview questions am I likely to face next?

OfferPath is built to answer those questions in a structured and personalized way.

Its core idea is:

```text
Resume + JD -> Skill Gap Analysis -> Actionable Roadmap -> Iterative Growth
```

This is not just an AI demo. It is meant to be a serious backend project that reflects real engineering concerns and real job-market demand.

---

## 2. Product vision

OfferPath helps users:

- upload a resume
- submit a target JD
- analyze skill gaps between the resume and the role
- generate a prioritized learning roadmap
- recommend proof-oriented project directions
- generate targeted interview preparation questions
- track progress over time and update recommendations

In later versions, the system can evolve into a personal career copilot that continuously monitors progress and refines the roadmap.

---

## 3. Core v1 scope

Version 1 focuses on a strong backend-first MVP.

### v1 user flow

1. User uploads a resume.
2. User submits a target job description.
3. System creates an analysis job.
4. Job is processed asynchronously.
5. AI workflow extracts skills from resume and JD.
6. System performs gap analysis.
7. System generates:
   - missing skills summary
   - prioritized learning roadmap
   - suggested project directions
   - likely interview topics/questions
8. User checks job status and reads the result.

### v1 features

- user registration and login
- resume upload
- JD submission
- async analysis job creation
- job status tracking
- AI-powered skill extraction and comparison
- roadmap generation
- project recommendation generation
- interview question generation
- result persistence and history
- retry and failure visibility

---

## 4. What makes this project valuable

This project is intentionally designed to cover both **AI/agent trends** and **real backend engineering skills**.

### AI / agent side

- resume understanding
- JD understanding
- skill extraction
- gap analysis
- roadmap generation
- multi-step workflow
- tool usage orchestration
- stateful progress tracking (later versions)

### Backend engineering side

- REST API design
- async processing
- queue-based decoupling
- job state machine
- PostgreSQL schema design
- Redis for caching / idempotency / rate limiting
- S3-backed resume object storage
- Dockerized services
- CI/CD pipeline
- AWS deployment
- HTTP / HTTPS / reverse proxy concepts
- logs, retries, and failure handling

---

## 5. Why this is more than “just calling an LLM API”

OfferPath is not meant to be a thin wrapper around a model.

A weak version of this product would simply do:

- upload resume
- paste JD
- call model once
- return text

OfferPath aims to be stronger than that.

It treats the task as an engineered workflow:

- input storage
- task creation
- async job execution
- structured intermediate analysis
- result persistence
- tool-assisted orchestration
- future progress updates

That makes it closer to an **agentic backend system** than a simple AI demo.

---

## 6. v1 architecture direction

### Suggested stack

- **Backend API:** FastAPI
- **Database:** PostgreSQL
- **Cache / control:** Redis
- **Object storage:** Amazon S3
- **Queue:** Amazon SQS
- **Worker:** Python worker service
- **AI provider:** model API (pluggable)
- **Deployment:** Docker + AWS EC2 first, ECS later
- **CI/CD:** GitHub Actions
- **Reverse proxy / HTTPS:** Nginx + optional domain/SSL

### High-level flow

1. Client uploads resume and JD.
2. Backend stores metadata in PostgreSQL.
3. Resume file is stored in S3.
4. Backend creates an analysis job.
5. Job ID is pushed to SQS.
6. Worker consumes the job.
7. Worker extracts structured information.
8. Worker calls model tools for comparison and planning.
9. Worker stores the result in PostgreSQL.
10. Client queries job status and result.

---

## 7. What “agentic” means in this project

OfferPath should not pretend to be a fully autonomous general agent.

For this project, “agentic” means:

- the system accepts a goal, not just a question
- the system decomposes the problem into multiple steps
- the system uses multiple tools/modules during analysis
- the system stores job state and intermediate progress
- the system generates action-oriented output instead of generic text
- future versions can update recommendations based on user progress

This keeps the agent concept grounded and credible.

---

## 8. Target interview value

This project is designed to support discussion around:

- why async processing is needed for long-running AI tasks
- how queue-based decoupling improves reliability
- how to prevent duplicate job creation with idempotency
- when to use Redis vs PostgreSQL vs S3
- how to design job states and retry strategies
- how CI/CD reduces deployment risk
- how HTTP and HTTPS fit into production deployment
- how to evolve from a single backend service to a more scalable architecture

---

## 9. Six-week development strategy

### Week 1 — Define and build the base system

- finalize project scope
- create repository structure
- write README v0.1
- design database schema
- implement auth and basic APIs
- implement resume upload and JD submission
- create job records
- make the end-to-end flow run locally with mock analysis

### Week 2 — Build async job processing

- add worker service
- add SQS-based job dispatch
- implement real analysis flow
- generate structured output:
  - skill gap summary
  - roadmap
  - project suggestions
  - interview questions
- add job status transitions and error handling

### Week 3 — Engineering and AWS deployment

- dockerize API and worker services
- add Docker Compose for local API / worker / PostgreSQL / Redis
- make configuration work across local SQLite, Docker PostgreSQL, and future AWS RDS
- add Redis connectivity as the foundation for idempotency, rate limiting, and job locks
- add structured logging for API and worker execution
- document local, Docker, and production-like environment variables
- keep AWS deployment-ready boundaries for S3 / RDS / SQS without requiring cloud setup yet

### Week 4 — Local Agentic AI workflow

- replace mock analysis with a pluggable AI provider interface
- keep the mock provider available for local testing and CI
- split analysis into a multi-step workflow:
  - resume understanding
  - JD understanding
  - skill gap comparison
  - roadmap generation
  - project recommendation
  - interview preparation
- require structured JSON output from the AI workflow
- validate AI results before storing them
- add prompt and workflow version tracking
- add retry and failure handling for model calls
- keep the agentic behavior grounded in job state, stored results, and explainable intermediate steps

### Week 5 — Testing and CI/CD

- expand automated tests for auth, uploads, jobs, worker processing, health checks, and AI workflow validation
- add GitHub Actions for test execution
- add Docker build checks for API and worker images
- add Docker Compose configuration validation
- perform simple local load testing against key endpoints
- refine README, architecture explanation, and demo flow
- prepare resume bullet points and interview talking points

### Week 6 — AWS deployment

- deploy the API and worker first on EC2 using Docker Compose
- configure environment variables and secrets for the EC2 deployment
- run PostgreSQL and Redis in the initial Compose-based EC2 setup if managed services are not ready
- prepare migration path from local containers to AWS managed services:
  - PostgreSQL container -> Amazon RDS
  - local resume storage -> Amazon S3
  - database-backed queue simulation -> Amazon SQS
  - Redis container -> Amazon ElastiCache
- add production deployment notes for logs, ports, HTTPS, Nginx, and domain/SSL
- document rollback and operational checks for the demo deployment

---

## 10. What not to do in v1

To keep the project finishable and credible, v1 should **not** include:

- full frontend complexity
- multi-agent collaboration hype
- vector database / RAG unless clearly needed
- OCR-heavy pipelines unless required
- too many third-party integrations
- complicated recommendation engines before the core workflow is stable

v1 wins by being **focused, deployable, and explainable**.

---

## 11. Long-term evolution

Possible future directions:

- GitHub profile analysis
- study plan sync with calendar tools
- weekly progress reports by email
- project portfolio scoring
- deeper interview simulation
- recruiter-facing candidate readiness reports
- role-specific plans (backend / data / cloud / AI engineer)

---

## 12. Project principle

OfferPath is built around one principle:

> Do not just help users look stronger on paper. Help them become stronger in reality.

That is the real value of the project, and that is what keeps the idea meaningful.

---

## 13. Local development

The repository currently contains the backend MVP:

- FastAPI application
- local SQLite persistence
- user registration and login
- authenticated resume upload
- JD submission
- analysis job creation
- worker-based agentic analysis workflow with a mock provider
- job status and result API
- job attempt tracking and worker timing fields
- workflow, prompt, provider, and intermediate-step tracking

### Run the backend locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open the API docs at:

```text
http://127.0.0.1:8000/docs
```

### Run tests

```bash
cd backend
source .venv/bin/activate
pytest
```

### Run the local worker

Week 2 introduces a worker entrypoint. The API creates queued jobs, and the
worker processes them:

```bash
cd backend
source .venv/bin/activate
python -m worker.main --once
```

### Run with Docker Compose

Week 3 adds a Docker Compose setup for local production-like services:

```bash
docker compose up --build
```

This starts:

- FastAPI API on `http://127.0.0.1:8000`
- worker service
- PostgreSQL on port `5432`
- Redis on port `6379`

The Docker environment uses:

```text
backend/.env.docker.example
```

The API docs are still available at:

```text
http://127.0.0.1:8000/docs
```

### Environment profiles

OfferPath currently supports three environment shapes:

| Environment | Database | Redis | Typical command |
| --- | --- | --- | --- |
| Local development | SQLite file | Local Redis URL configured but not required yet | `uvicorn app.main:app --reload` |
| Docker development | PostgreSQL container | Redis container | `docker compose up --build` |
| Production-like AWS | RDS PostgreSQL | ElastiCache Redis | future deployment step |

The active database is controlled by:

```text
OFFERPATH_DATABASE_URL
```

Local default:

```text
sqlite:///./offerpath.db
```

Docker default:

```text
postgresql+psycopg://offerpath:offerpath@postgres:5432/offerpath
```

Redis is configured through:

```text
OFFERPATH_REDIS_URL
```

Redis is included in Docker Compose. The application uses Redis through a small client wrapper that currently supports:

- readiness checks
- rate limiting for AI analysis job creation
- idempotency keys for `POST /jobs`
- live job status/progress cache
- owner-safe distributed locks for worker execution

Redis is temporary operational storage only. PostgreSQL/SQLite remains the
source of truth for users, resumes, job state, `result_json`,
`intermediate_json`, and metadata.

Redis-backed reliability features:

- rate limiting protects AI provider cost from repeated job creation
- `Idempotency-Key` prevents duplicate jobs when a client retries `POST /jobs`
- live status cache exposes progress such as `parsing_resume` and
  `running_analysis_provider`
- distributed worker lock prevents duplicate execution when multiple workers
  compete for the same analysis job

Manual Redis test flow:

```bash
redis-server
```

Then start the API:

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --reload
```

Create a job with:

```text
Idempotency-Key: test-key-123
```

Send the same `POST /jobs` request again with the same header. The response
should return the same job id instead of creating a duplicate. Run the worker:

```bash
PYTHONPATH=. python -m worker.main --once
```

Then check:

```text
GET /jobs/{job_id}
```

The response keeps the existing fields and adds `live_status` when Redis has
progress data.

AI analysis is configured through:

```text
OFFERPATH_AI_PROVIDER
OFFERPATH_GEMINI_MODEL
OFFERPATH_GEMINI_API_KEY
```

The default provider is `mock`, which keeps local development and CI stable.
Set `OFFERPATH_AI_PROVIDER=gemini` and provide `OFFERPATH_GEMINI_API_KEY` to
call Gemini through the pluggable provider interface. Do not commit real API
keys to `.env` examples or source control.

The Week 4 analysis workflow records:

- provider name
- workflow version
- prompt version
- intermediate steps
- validated structured result JSON

### Real demo flow: PDF resume to AI SRE action plan

This flow demonstrates the real OfferPath product goal: upload a PDF resume,
submit a target JD, run the async worker, and read a structured career gap
analysis.

Start Redis and the API locally:

```bash
docker compose up redis
cd backend
source .venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --reload
```

Open the API docs:

```text
http://127.0.0.1:8000/docs
```

Use Swagger or curl to run the flow:

1. Register a user with `POST /auth/register`.
2. Login with `POST /auth/login` and copy the `access_token`.
3. Authorize Swagger with `Bearer <access_token>`.
4. Upload a text-based PDF resume with `POST /resumes`.
5. Create an AI SRE analysis job with `POST /jobs`.

Example AI SRE job body:

```json
{
  "resume_id": 1,
  "target_title": "AI SRE",
  "job_description": "We need an AI SRE who can run production AI systems on AWS, build observability dashboards, debug incidents, operate Kubernetes workloads, design async queues, understand LLM workflows, write Python services, manage Redis/PostgreSQL, automate CI/CD, and explain reliability trade-offs."
}
```

Run the worker once:

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. python -m worker.main --once
```

Then query the result:

```text
GET /jobs/{job_id}
```

Successful jobs return `status: "succeeded"` and a structured `result` with:

- `matched_skills`
- prioritized `missing_skills`
- `weak_skills` and `partially_matched_skills`
- `evidence_from_resume` and `evidence_from_jd`
- `30_day_roadmap`
- `project_tasks`
- `interview_talking_points`
- `resume_improvement_suggestions`

The worker also saves useful `intermediate_steps` for:

- `resume_understanding`
- `jd_understanding`
- `skill_gap_comparison`
- `roadmap_generation`
- `project_recommendation`
- `interview_preparation`
- `final_result_validation`

To use the stable local mock provider:

```text
OFFERPATH_AI_PROVIDER=mock
```

To use Gemini for real AI output, set these values in your local
`backend/.env` only:

```text
OFFERPATH_AI_PROVIDER=gemini
OFFERPATH_GEMINI_MODEL=gemini-1.5-flash
OFFERPATH_GEMINI_API_KEY=your-local-secret
```

Do not hardcode API keys in Python code. Do not commit real keys to
`.env.example`, `.env.docker.example`, README examples, or source control.
The example env files should contain placeholders only. Local secrets belong in
`backend/.env`.

### S3-backed resume storage

Resume files are stored outside the database. The upload API sends the original
PDF/TXT bytes to S3 through the storage service, then stores only metadata in
PostgreSQL/SQLite:

- original filename
- storage backend
- S3 key in `stored_path`
- content type
- file size
- owner and timestamps

Storage is configured through:

```text
STORAGE_BACKEND=s3
AWS_REGION=ap-southeast-2
S3_BUCKET_NAME=your-bucket-name
S3_RESUME_PREFIX=resumes
```

For local personal AWS credentials, the app also supports:

```text
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

Production deployments should prefer EC2/ECS IAM roles rather than committed or
hard-coded credentials. Tests use the local storage backend and do not require a
real AWS bucket.

The worker analysis flow is now:

```text
AnalysisJob.resume.stored_path
-> S3StorageService.read_file()
-> ResumeParser.extract_resume_text()
-> mock/Gemini provider.run(resume_text, job_description)
-> Pydantic validation
-> result_json / intermediate_json saved in the database
```

The parser supports `.txt` and `.pdf` resumes. Gemini and mock providers still
receive plain `resume_text`; they do not read S3 keys or parse PDFs directly.
This keeps the design ready for future agent tools such as
`read_resume_tool(job_id)`, while intentionally avoiding skills, MCP, or
multi-agent architecture in this version.

Readiness endpoint:

```text
GET /health/ready
```

### Logging

API and worker logs are emitted through Python logging with JSON event payloads. The log level is controlled by:

```text
OFFERPATH_LOG_LEVEL
```

Example worker log event:

```json
{"env": "docker", "event": "analysis_job.succeeded", "attempt_count": 1, "job_id": 42, "missing_skill_count": 5, "status": "succeeded"}
```

Important event names include:

- `api.startup`
- `api.shutdown`
- `analysis_job.enqueued`
- `worker.started`
- `worker.job_claimed`
- `analysis_job.started`
- `analysis_job.succeeded`
- `analysis_job.failed`

### Week 3 verification checklist

Run the local test suite:

```bash
cd backend
source .venv/bin/activate
pytest
```

Validate the Docker Compose file:

```bash
docker compose config --quiet
```

Start the production-like local stack:

```bash
docker compose up --build
```

Check the API:

```text
http://127.0.0.1:8000/docs
```

Check readiness:

```text
GET http://127.0.0.1:8000/health/ready
```

Expected Docker readiness:

```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok"
}
```

Expected local readiness without Redis running:

```json
{
  "status": "ok",
  "database": "ok",
  "redis": "unavailable"
}
```

### Week 1 API flow

1. `POST /auth/register`
2. `POST /auth/login`
3. `POST /resumes`
4. `POST /jobs`
5. `GET /jobs/{job_id}`
6. `python -m worker.main --once`
7. `GET /jobs/{job_id}`

The analysis logic is intentionally mocked so the full product flow works locally before adding real cloud queue, cloud storage, and AI provider integrations.
