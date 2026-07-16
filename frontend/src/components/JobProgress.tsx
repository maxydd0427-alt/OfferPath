import type { JobDetail, JobRead } from "../types/analysis";

type JobProgressProps = {
  job: JobDetail | JobRead | null;
  polling: boolean;
  busy: boolean;
  onStart: () => Promise<void>;
};

const steps = [
  { key: "uploaded", label: "Resume uploaded" },
  { key: "queued", label: "Job created" },
  { key: "processing", label: "AI workflow running" },
  { key: "succeeded", label: "Result ready" },
];

export function JobProgress({ job, polling, busy, onStart }: JobProgressProps) {
  const status = job?.status ?? "queued";
  const liveStatus = "live_status" in (job ?? {}) ? (job as JobDetail).live_status : null;
  const progress = typeof liveStatus?.progress === "number" ? liveStatus.progress : status === "succeeded" ? 100 : 30;
  const canStart = Boolean(job && ["queued", "failed"].includes(status));

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-pine">Progress</p>
          <h2 className="mt-2 text-lg font-extrabold text-slate-950">
            {job ? `Job #${job.id}` : "Ready when you are"}
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {polling ? (
            <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-extrabold text-emerald-800">
              polling
            </span>
          ) : null}
          {canStart ? (
            <button className="primary-button min-h-9 px-3 py-1.5 text-xs" type="button" disabled={busy} onClick={onStart}>
              Start analysis
            </button>
          ) : null}
        </div>
      </div>

      <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {steps.map((step, index) => {
          const active =
            step.key === "uploaded" ||
            (step.key === "queued" && job) ||
            (step.key === "processing" && ["processing", "succeeded"].includes(status)) ||
            (step.key === "succeeded" && status === "succeeded");
          return (
            <div
              key={step.key}
              className={`rounded-[8px] border p-2.5 transition ${
                active ? "border-pine/30 bg-emerald-50 text-pine" : "border-slate-200 bg-white text-slate-500"
              }`}
            >
              <p className="text-[10px] font-extrabold uppercase tracking-[0.12em]">Step {index + 1}</p>
              <p className="mt-1 whitespace-normal break-normal text-[11px] font-bold leading-4">{step.label}</p>
            </div>
          );
        })}
      </div>

      <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-pine transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>

      <p className="mt-4 text-sm leading-6 text-slate-600">
        {liveStatus?.message || liveStatus?.step || (job ? `Current status: ${status}` : "Create a job to begin.")}
      </p>
    </section>
  );
}
