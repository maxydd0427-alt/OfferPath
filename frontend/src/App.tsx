import { useEffect, useMemo, useState } from "react";
import { AnalysisForm } from "./components/AnalysisForm";
import { AuthCard } from "./components/AuthCard";
import { EmptyState } from "./components/EmptyState";
import { Hero } from "./components/Hero";
import { JobProgress } from "./components/JobProgress";
import { LoadingState } from "./components/LoadingState";
import { ResultDashboard } from "./components/ResultDashboard";
import { Shell } from "./components/Shell";
import { api } from "./lib/api";
import { demoJob } from "./lib/mockData";
import { clearToken, getToken, setToken } from "./lib/storage";
import type { JobDetail, JobRead, Resume, User } from "./types/analysis";

export default function App() {
  const [token, setSessionToken] = useState(getToken());
  const [user, setUser] = useState<User | null>(null);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [job, setJob] = useState<JobDetail | JobRead | null>(null);
  const [jobDetail, setJobDetail] = useState<JobDetail | null>(null);
  const [authError, setAuthError] = useState("");
  const [flowError, setFlowError] = useState("");
  const [busy, setBusy] = useState(false);
  const [polling, setPolling] = useState(false);
  const [analysisStarted, setAnalysisStarted] = useState(false);
  const [demoMode, setDemoMode] = useState(false);

  const isTerminal = jobDetail?.status === "succeeded" || jobDetail?.status === "failed";
  const disabled = !token || demoMode;

  useEffect(() => {
    if (!token) return;
    api
      .me(token)
      .then(setUser)
      .then(() => api.listResumes(token))
      .then((items) => {
        setResumes(items);
        setSelectedResumeId((current) => current ?? items[0]?.id ?? null);
      })
      .catch(() => {
        clearToken();
        setSessionToken("");
        setUser(null);
      });
  }, [token]);

  useEffect(() => {
    if (!token || !job || isTerminal || demoMode || !analysisStarted) {
      setPolling(false);
      return;
    }
    setPolling(true);
    const timer = window.setInterval(() => {
      api
        .getJob(token, job.id)
        .then((detail) => {
          setJob(detail);
          setJobDetail(detail);
        })
        .catch((error: Error) => setFlowError(error.message));
    }, 2500);
    return () => {
      window.clearInterval(timer);
      setPolling(false);
    };
  }, [token, job, isTerminal, demoMode, analysisStarted]);

  const latestJob = useMemo(() => jobDetail ?? job, [jobDetail, job]);

  async function handleRegister(email: string, password: string) {
    setAuthError("");
    setBusy(true);
    try {
      await api.register(email, password);
      await handleLogin(email, password);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Registration failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleLogin(email: string, password: string) {
    setAuthError("");
    setBusy(true);
    try {
      const nextToken = await api.login(email, password);
      setToken(nextToken);
      setSessionToken(nextToken);
      const nextUser = await api.me(nextToken);
      const nextResumes = await api.listResumes(nextToken);
      setUser(nextUser);
      setResumes(nextResumes);
      setSelectedResumeId(nextResumes[0]?.id ?? null);
      setDemoMode(false);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  }

  function handleLogout() {
    clearToken();
    setSessionToken("");
    setUser(null);
    setResumes([]);
    setSelectedResumeId(null);
    setJob(null);
    setJobDetail(null);
    setAnalysisStarted(false);
    setDemoMode(false);
  }

  async function handleUpload(file: File) {
    if (!token) return;
    setFlowError("");
    setBusy(true);
    try {
      const resume = await api.uploadResume(token, file);
      const nextResumes = await api.listResumes(token);
      setResumes(nextResumes);
      setSelectedResumeId(resume.id);
    } catch (error) {
      setFlowError(error instanceof Error ? error.message : "Resume upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitJob(resumeId: number, targetTitle: string, jobDescription: string) {
    if (!token) return;
    setFlowError("");
    setBusy(true);
    try {
      const createdJob = await api.createJob(token, {
        resume_id: resumeId,
        target_title: targetTitle,
        job_description: jobDescription,
      });
      setJob(createdJob);
      setJobDetail(null);
      setAnalysisStarted(false);
      const detail = await api.getJob(token, createdJob.id);
      setJob(detail);
      setJobDetail(detail);
    } catch (error) {
      setFlowError(error instanceof Error ? error.message : "Job creation failed.");
    } finally {
      setBusy(false);
    }
  }

  function showDemo() {
    setDemoMode(true);
    setJob(demoJob);
    setJobDetail(demoJob);
    setAnalysisStarted(false);
    setFlowError("");
    window.setTimeout(() => document.getElementById("results")?.scrollIntoView({ behavior: "smooth" }), 80);
  }

  async function handleStartAnalysis() {
    if (!token || !latestJob) return;
    setFlowError("");
    setBusy(true);
    try {
      const startedJob = await api.runJob(token, latestJob.id);
      setJob(startedJob);
      setAnalysisStarted(true);
      const detail = await api.getJob(token, startedJob.id);
      setJob(detail);
      setJobDetail(detail);
    } catch (error) {
      setFlowError(error instanceof Error ? error.message : "Could not start analysis.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell user={user}>
      <Hero onDemo={showDemo} />

      <section className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <div className="grid content-start gap-5">
          <AuthCard
            user={user}
            busy={busy}
            error={authError}
            onLogin={handleLogin}
            onRegister={handleRegister}
            onLogout={handleLogout}
          />
          <JobProgress job={latestJob} polling={polling} busy={busy} onStart={handleStartAnalysis} />
        </div>

        <div className="grid gap-5">
          <AnalysisForm
            resumes={resumes}
            selectedResumeId={selectedResumeId}
            busy={busy}
            disabled={disabled}
            onUpload={handleUpload}
            onSelectResume={setSelectedResumeId}
            onSubmitJob={handleSubmitJob}
          />
          {flowError ? (
            <div className="card border-red-100 bg-red-50 p-4 text-sm font-bold text-red-700">{flowError}</div>
          ) : null}
        </div>
      </section>

      <section className="grid gap-4" id="results">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-pine">Result dashboard</p>
            <h2 className="mt-2 text-2xl font-extrabold text-slate-950">Career action plan</h2>
          </div>
          {demoMode ? (
            <span className="rounded-full bg-white px-4 py-2 text-sm font-extrabold text-pine shadow-sm">
              Demo mode
            </span>
          ) : null}
        </div>
        {busy && !jobDetail ? <LoadingState /> : <ResultDashboard job={jobDetail} />}
        {!token && !demoMode ? (
          <EmptyState title="Connect to the backend" message="Login or use View Demo Result to preview the interface." />
        ) : null}
      </section>
    </Shell>
  );
}
