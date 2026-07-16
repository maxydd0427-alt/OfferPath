# OfferPath Frontend

Lightweight Vite + React + TypeScript demo client for the OfferPath FastAPI backend.

## Run Locally

```bash
cd frontend
npm install
npm run dev
```

The frontend expects the backend API at:

```text
http://localhost:8000
```

Override it with:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Backend Flow

The UI talks to the real backend routes:

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `POST /resumes`
- `GET /resumes`
- `POST /jobs`
- `GET /jobs`
- `GET /jobs/{job_id}`

Demo mode loads local mock data only so the UI can be presented without a running worker or LLM key.
