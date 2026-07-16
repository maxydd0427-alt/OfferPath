import type { ReactNode } from "react";
import type { JobDetail } from "../types/analysis";
import { arrayValue, asRecord, displayValue } from "../lib/render";
import { EmptyState } from "./EmptyState";
import { RoadmapCard } from "./RoadmapCard";
import { SkillBadge } from "./SkillBadge";

type ResultDashboardProps = {
  job: JobDetail | null;
};

export function ResultDashboard({ job }: ResultDashboardProps) {
  if (!job) {
    return (
      <EmptyState
        title="No result yet"
        message="Upload a resume and create an analysis job, or use the demo result to preview the dashboard."
      />
    );
  }

  if (job.status === "failed") {
    return (
      <div className="card border-red-100 bg-red-50 p-6">
        <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-red-600">Job failed</p>
        <h2 className="mt-2 text-xl font-extrabold text-red-950">The analysis could not complete</h2>
        <p className="mt-3 text-sm leading-6 text-red-800">{job.error_message || job.last_error || "Unknown error."}</p>
      </div>
    );
  }

  const result = job.result;
  if (!result) {
    return (
      <EmptyState
        title="Waiting for result"
        message="The worker is still processing this job. Keep the backend worker running and the dashboard will update."
      />
    );
  }

  const matchedSkills = arrayValue(result.matched_skills);
  const missingSkills = arrayValue(result.missing_skills);
  const weakSkills = [...arrayValue(result.weak_skills), ...arrayValue(result.partially_matched_skills)];
  const roadmap = arrayValue(result["30_day_roadmap"]).length
    ? arrayValue(result["30_day_roadmap"])
    : arrayValue(result.thirty_day_roadmap).length
      ? arrayValue(result.thirty_day_roadmap)
      : arrayValue(result.roadmap);
  const projectSuggestions = [...arrayValue(result.project_suggestions), ...arrayValue(result.project_tasks)];
  const interviewQuestions = [...arrayValue(result.interview_questions), ...arrayValue(result.interview_talking_points)];

  return (
    <section className="grid gap-5">
      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <DashboardCard title="Match Summary">
          <p className="text-sm leading-7 text-slate-600">
            {result.summary || "OfferPath generated a structured result. Review the detailed cards below."}
          </p>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <Metric label="Provider" value={job.ai_provider} />
            <Metric label="Workflow" value={job.workflow_version} />
            <Metric label="Prompt" value={job.prompt_version} />
          </div>
        </DashboardCard>

        <DashboardCard title="Matched Skills">
          <BadgeList values={matchedSkills} tone="match" empty="No matched skills returned." />
        </DashboardCard>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <DashboardCard title="Missing Skills">
          <BadgeList values={missingSkills} tone="gap" empty="No missing skills returned." />
        </DashboardCard>
        <DashboardCard title="Priority Skill Gaps">
          <div className="grid gap-3">
            {missingSkills.length ? (
              missingSkills.map((item, index) => {
                const record = asRecord(item);
                return (
                  <div key={`${displayValue(record?.skill ?? item)}-${index}`} className="rounded-[8px] bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-extrabold text-slate-950">
                        {displayValue(record?.skill ?? item) || "Skill gap"}
                      </span>
                      {record?.priority ? <SkillBadge tone="gap">{displayValue(record.priority)}</SkillBadge> : null}
                    </div>
                    {record?.reason ? <p className="mt-2 text-sm leading-6 text-slate-600">{displayValue(record.reason)}</p> : null}
                  </div>
                );
              })
            ) : (
              <p className="text-sm text-slate-500">No prioritized gaps returned.</p>
            )}
          </div>
        </DashboardCard>
      </div>

      {weakSkills.length ? (
        <DashboardCard title="Weak or Partially Matched Skills">
          <BadgeList values={weakSkills} tone="weak" empty="" />
        </DashboardCard>
      ) : null}

      <DashboardCard title="30-Day Learning Roadmap">
        <div className="grid gap-4 md:grid-cols-2">
          {roadmap.length ? (
            roadmap.map((item, index) => <RoadmapCard key={index} item={item} index={index} />)
          ) : (
            <p className="text-sm text-slate-500">No roadmap returned.</p>
          )}
        </div>
      </DashboardCard>

      <div className="grid gap-5 lg:grid-cols-2">
        <DashboardCard title="Project Suggestions">
          <SimpleList values={projectSuggestions} empty="No project suggestions returned." />
        </DashboardCard>
        <DashboardCard title="Interview Questions">
          <SimpleList values={interviewQuestions} empty="No interview prep returned." />
        </DashboardCard>
      </div>

      <DashboardCard title="Intermediate Agent Steps">
        {job.intermediate_steps ? (
          <pre className="max-h-96 overflow-auto rounded-[8px] bg-slate-950 p-4 text-xs leading-6 text-slate-100">
            {JSON.stringify(job.intermediate_steps, null, 2)}
          </pre>
        ) : (
          <p className="text-sm text-slate-500">No intermediate steps returned.</p>
        )}
      </DashboardCard>

      <DashboardCard title="Raw Result Fallback">
        <pre className="max-h-96 overflow-auto rounded-[8px] bg-slate-50 p-4 text-xs leading-6 text-slate-700">
          {JSON.stringify(result, null, 2)}
        </pre>
      </DashboardCard>
    </section>
  );
}

function DashboardCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="card p-5">
      <h3 className="text-base font-extrabold text-slate-950">{title}</h3>
      <div className="mt-3">{children}</div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[8px] border border-slate-100 bg-white p-3">
      <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-slate-400">{label}</p>
      <p className="mt-1 break-words text-sm font-bold text-slate-800">{value || "-"}</p>
    </div>
  );
}

function BadgeList({ values, tone, empty }: { values: unknown[]; tone: "match" | "gap" | "weak"; empty: string }) {
  if (!values.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {values.map((item, index) => {
        const record = asRecord(item);
        const label = displayValue(record?.skill ?? record?.name ?? item);
        return label ? (
          <SkillBadge key={`${label}-${index}`} tone={tone}>
            {label}
          </SkillBadge>
        ) : null;
      })}
    </div>
  );
}

function SimpleList({ values, empty }: { values: unknown[]; empty: string }) {
  if (!values.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <div className="grid gap-3">
      {values.map((item, index) => {
        const record = asRecord(item);
        const title = displayValue(record?.title ?? record?.skill);
        const description = displayValue(record?.description ?? record?.task ?? item);
        return (
          <div key={index} className="rounded-[8px] bg-slate-50 p-4">
            {title ? <p className="font-extrabold text-slate-950">{title}</p> : null}
            <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
          </div>
        );
      })}
    </div>
  );
}
