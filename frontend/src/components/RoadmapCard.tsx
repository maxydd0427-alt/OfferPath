import { asRecord, displayValue } from "../lib/render";

type RoadmapCardProps = {
  item: unknown;
  index: number;
};

export function RoadmapCard({ item, index }: RoadmapCardProps) {
  const record = asRecord(item);
  const days = displayValue(record?.days) || `Step ${index + 1}`;
  const skill = displayValue(record?.skill) || displayValue(record?.title) || "Focus area";
  const task = displayValue(record?.task) || displayValue(record?.description) || displayValue(item);
  const priority = displayValue(record?.priority);

  return (
    <article className="card relative overflow-hidden p-5 transition hover:-translate-y-1 hover:shadow-soft">
      <div className="absolute left-0 top-0 h-full w-1 bg-pine" />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-pine">{days}</p>
          <h4 className="mt-2 text-lg font-extrabold text-slate-950">{skill}</h4>
        </div>
        {priority ? (
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-extrabold text-slate-700">
            {priority}
          </span>
        ) : null}
      </div>
      <p className="mt-4 text-sm leading-6 text-slate-600">{task}</p>
    </article>
  );
}
