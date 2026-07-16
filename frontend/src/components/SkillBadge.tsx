type SkillBadgeProps = {
  children: string;
  tone?: "match" | "gap" | "weak" | "neutral";
};

const tones = {
  match: "border-emerald-200 bg-emerald-50 text-emerald-800",
  gap: "border-coral/25 bg-coral/10 text-red-800",
  weak: "border-amber-200 bg-amber-50 text-amber-800",
  neutral: "border-slate-200 bg-slate-50 text-slate-700",
};

export function SkillBadge({ children, tone = "neutral" }: SkillBadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-extrabold ${tones[tone]}`}>
      {children}
    </span>
  );
}
