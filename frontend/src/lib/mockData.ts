import type { JobDetail } from "../types/analysis";

export const demoJob: JobDetail = {
  id: 1001,
  resume_id: 42,
  target_title: "Software Engineer",
  status: "succeeded",
  attempt_count: 1,
  max_attempts: 3,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  started_at: new Date().toISOString(),
  finished_at: new Date().toISOString(),
  ai_provider: "career-agent",
  workflow_version: "career-agent-react-v0",
  prompt_version: "career-agent-mcp-v0",
  live_status: {
    status: "succeeded",
    step: "completed",
    progress: 100,
    message: "Analysis completed.",
  },
  error_message: null,
  last_error: null,
  result: {
    summary:
      "Your computer science foundation is strong. To become interview-ready for this software engineering role, focus on system design clarity, database-backed project evidence, testing discipline, and crisp project storytelling.",
    matched_skills: ["Python", "FastAPI", "Redis", "Docker", "Testing"],
    missing_skills: [
      {
        skill: "System design",
        priority: "P1",
        reason: "The target job expects clear trade-off thinking across APIs, storage, reliability, and deployment.",
      },
      {
        skill: "Testing",
        priority: "P1",
        reason: "The resume should show stronger proof of unit tests, integration tests, and debugging habits.",
      },
      {
        skill: "Cloud deployment",
        priority: "P2",
        reason: "The target job values practical experience deploying and operating a service.",
      },
    ],
    weak_skills: ["SQL", "CI/CD"],
    "30_day_roadmap": [
      {
        days: "Day 1-7",
        priority: "P1",
        skill: "System design",
        task: "Write a one-page design for a small job tracking service covering API shape, database tables, queues, and failure handling.",
      },
      {
        days: "Day 8-14",
        priority: "P1",
        skill: "Testing",
        task: "Add unit and integration tests to one portfolio project, then document the bugs the tests would have caught.",
      },
      {
        days: "Day 15-21",
        priority: "P2",
        skill: "Cloud deployment",
        task: "Deploy a small backend project and write setup notes, environment variables, and operational checks.",
      },
      {
        days: "Day 22-30",
        priority: "P2",
        skill: "Interview storytelling",
        task: "Prepare concise STAR stories for your strongest project, debugging experience, and teamwork example.",
      },
    ],
    project_suggestions: [
      "Build a job application tracker with authentication, saved jobs, status transitions, and a PostgreSQL schema.",
      "Create a REST API project with tests, logging, deployment notes, and a short architecture decision record.",
      "Turn one course or personal project into a portfolio case study with problem, design, trade-offs, and measurable result.",
    ],
    interview_questions: [
      "Tell me about a project where you made an important technical trade-off.",
      "How would you design the backend for a job application tracking product?",
      "Describe a time you debugged a difficult issue and how you found the root cause.",
    ],
  },
  intermediate_steps: {
    planner: "llm_react_planner",
    rag_runtime: "rag_v2",
    mcp_runtime: "real_mcp_client",
    tool_calls: [
      { step: 1, action: "get_resume_text_tool", reason: "Need resume evidence." },
      { step: 2, action: "get_job_description_tool", reason: "Need role requirements." },
      { step: 3, action: "rag_v2_retrieval", reason: "Use tenant-isolated evidence citations." },
      { step: 4, action: "build_structured_result_tool", reason: "Create validated roadmap." },
      { step: 5, action: "github_mcp_search_reference_projects", reason: "Find reference projects." },
    ],
    final_result_validation: {
      validated_schema: "AnalysisResult",
      writes_result_json: false,
    },
  },
};
