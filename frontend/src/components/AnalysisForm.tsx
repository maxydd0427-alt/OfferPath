import { FormEvent, useMemo, useState } from "react";
import type { Resume } from "../types/analysis";

type AnalysisFormProps = {
  resumes: Resume[];
  selectedResumeId: number | null;
  busy: boolean;
  disabled: boolean;
  onUpload: (file: File) => Promise<void>;
  onSubmitJob: (resumeId: number, targetTitle: string, jobDescription: string) => Promise<void>;
  onSelectResume: (resumeId: number) => void;
};

const defaultJD =
  "We need a software engineer who can build reliable web services, work with databases, write clean tests, use cloud tools, collaborate with product teams, and explain engineering trade-offs clearly.";

export function AnalysisForm({
  resumes,
  selectedResumeId,
  busy,
  disabled,
  onUpload,
  onSubmitJob,
  onSelectResume,
}: AnalysisFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [targetTitle, setTargetTitle] = useState("Software Engineer");
  const [jobDescription, setJobDescription] = useState(defaultJD);

  const sortedResumes = useMemo(() => [...resumes].sort((a, b) => b.id - a.id), [resumes]);
  const activeResumeId = useMemo(
    () => selectedResumeId ?? sortedResumes[0]?.id ?? null,
    [sortedResumes, selectedResumeId],
  );

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (file) await onUpload(file);
  }

  async function submitJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (activeResumeId) await onSubmitJob(activeResumeId, targetTitle, jobDescription);
  }

  return (
    <section className="card p-5" id="workspace">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-pine">Analysis</p>
          <h2 className="mt-2 text-xl font-extrabold text-slate-950">Upload resume and target JD</h2>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-extrabold text-slate-600">
          PDF/TXT supported
        </span>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[0.85fr_1.15fr]">
        <form className="grid content-start gap-4" onSubmit={upload}>
          <label className="label">
            Resume file
            <input
              className="field"
              type="file"
              accept=".pdf,.txt"
              disabled={disabled || busy}
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button className="secondary-button" type="submit" disabled={disabled || busy || !file}>
            Upload resume
          </button>

          <div className="grid gap-2">
            <p className="text-sm font-extrabold text-slate-700">Uploaded resumes</p>
            {sortedResumes.length ? (
              sortedResumes.map((resume) => (
                <button
                  key={resume.id}
                  className={`rounded-[8px] border p-3 text-left text-sm transition hover:border-pine/40 ${
                    activeResumeId === resume.id ? "border-pine bg-emerald-50" : "border-slate-200 bg-white"
                  }`}
                  type="button"
                  onClick={() => onSelectResume(resume.id)}
                >
                  <span className="font-extrabold text-slate-900">#{resume.id}</span>{" "}
                  <span className="text-slate-600">{resume.original_filename}</span>
                  <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-[0.1em] text-slate-500">
                    {resume.storage_backend}
                  </span>
                </button>
              ))
            ) : (
              <p className="rounded-[8px] border border-dashed border-slate-200 p-4 text-sm text-slate-500">
                Upload a resume to start.
              </p>
            )}
          </div>
        </form>

        <form className="grid gap-4" onSubmit={submitJob}>
          <label className="label">
            Target role
            <input
              className="field"
              value={targetTitle}
              disabled={disabled || busy}
              onChange={(event) => setTargetTitle(event.target.value)}
            />
          </label>
          <label className="label">
            Job description
            <textarea
              className="field min-h-44 resize-y"
              value={jobDescription}
              disabled={disabled || busy}
              onChange={(event) => setJobDescription(event.target.value)}
            />
          </label>
          <button className="primary-button" type="submit" disabled={disabled || busy || !activeResumeId}>
            Create analysis job
          </button>
        </form>
      </div>
    </section>
  );
}
