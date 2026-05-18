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
- S3 object storage
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

## 9. Four-week development strategy

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

- add Redis
- add idempotency and simple rate limiting
- dockerize services
- deploy backend and worker to AWS
- connect S3 / RDS / SQS
- add logging and environment separation

### Week 4 — CI/CD, testing, and polishing

- add GitHub Actions
- add basic automated tests
- add deployment automation
- perform simple load testing
- refine architecture explanation
- prepare resume bullet points and demo flow

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