import type { CreateJobPayload, JobDetail, JobRead, Resume, User } from "../types/analysis";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

type ApiErrorPayload = {
  detail?: string;
};

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message =
      typeof payload === "object" && payload !== null
        ? (payload as ApiErrorPayload).detail ?? JSON.stringify(payload)
        : String(payload);
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return payload as T;
}

function authHeaders(token: string, headers: HeadersInit = {}): HeadersInit {
  return token ? { ...headers, Authorization: `Bearer ${token}` } : headers;
}

export const api = {
  baseUrl: API_BASE_URL,

  async register(email: string, password: string): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    return parseResponse<User>(response);
  },

  async login(email: string, password: string): Promise<string> {
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    const payload = await parseResponse<{ access_token: string }>(response);
    return payload.access_token;
  },

  async me(token: string): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: authHeaders(token),
    });
    return parseResponse<User>(response);
  },

  async uploadResume(token: string, file: File): Promise<Resume> {
    const form = new FormData();
    form.set("file", file);
    const response = await fetch(`${API_BASE_URL}/resumes`, {
      method: "POST",
      headers: authHeaders(token),
      body: form,
    });
    return parseResponse<Resume>(response);
  },

  async listResumes(token: string): Promise<Resume[]> {
    const response = await fetch(`${API_BASE_URL}/resumes`, {
      headers: authHeaders(token),
    });
    return parseResponse<Resume[]>(response);
  },

  async createJob(token: string, payload: CreateJobPayload): Promise<JobRead> {
    const response = await fetch(`${API_BASE_URL}/jobs`, {
      method: "POST",
      headers: authHeaders(token, {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      }),
      body: JSON.stringify(payload),
    });
    return parseResponse<JobRead>(response);
  },

  async listJobs(token: string): Promise<JobRead[]> {
    const response = await fetch(`${API_BASE_URL}/jobs`, {
      headers: authHeaders(token),
    });
    return parseResponse<JobRead[]>(response);
  },

  async getJob(token: string, jobId: number): Promise<JobDetail> {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
      headers: authHeaders(token),
    });
    return parseResponse<JobDetail>(response);
  },

  async runJob(token: string, jobId: number): Promise<JobRead> {
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/run`, {
      method: "POST",
      headers: authHeaders(token),
    });
    return parseResponse<JobRead>(response);
  },
};
