export type JobStatus = "queued" | "processing" | "succeeded" | "failed";

export type User = {
  id: number;
  email: string;
  created_at: string;
};

export type Resume = {
  id: number;
  original_filename: string;
  storage_backend: string;
  content_type: string | null;
  file_size: number;
  created_at: string;
};

export type JobRead = {
  id: number;
  resume_id: number;
  target_title: string;
  status: JobStatus;
  attempt_count: number;
  max_attempts: number;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type LiveStatus = {
  status?: string;
  step?: string;
  progress?: number | null;
  message?: string;
};

export type AnalysisResult = Record<string, unknown> & {
  summary?: string;
  matched_skills?: unknown[];
  missing_skills?: unknown[];
  weak_skills?: unknown[];
  partially_matched_skills?: unknown[];
  roadmap?: unknown[];
  thirty_day_roadmap?: unknown[];
  "30_day_roadmap"?: unknown[];
  project_suggestions?: unknown[];
  project_tasks?: unknown[];
  interview_questions?: unknown[];
  interview_talking_points?: unknown[];
};

export type JobDetail = JobRead & {
  result: AnalysisResult | null;
  intermediate_steps: Record<string, unknown> | null;
  live_status: LiveStatus | null;
  ai_provider: string;
  workflow_version: string;
  prompt_version: string;
  error_message?: string | null;
  last_error?: string | null;
};

export type CreateJobPayload = {
  resume_id: number;
  target_title: string;
  job_description: string;
};
