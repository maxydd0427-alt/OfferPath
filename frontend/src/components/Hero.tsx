type HeroProps = {
  onDemo: () => void;
};

export function Hero({ onDemo }: HeroProps) {
  return (
    <section className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
      <div>
        <div className="inline-flex items-center gap-2 rounded-full border border-white/80 bg-white/70 px-3 py-1 text-xs font-extrabold uppercase tracking-[0.18em] text-pine shadow-sm">
          CS career growth
        </div>
        <h1 className="mt-4 max-w-4xl text-3xl font-extrabold leading-tight text-slate-950 sm:text-4xl lg:text-5xl">
          OfferPath
        </h1>
        <p className="mt-4 max-w-2xl text-lg leading-7 text-slate-600">
          Turn your resume and dream job into a clear action plan.
        </p>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
          Upload a resume, paste a target job description, and get a structured gap analysis with a 30-day roadmap,
          portfolio projects, interview prep, and transparent agent steps.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <a href="#workspace" className="primary-button">
            Start analysis
          </a>
          <button className="secondary-button" type="button" onClick={onDemo}>
            View Demo Result
          </button>
        </div>
      </div>

      <div className="card relative overflow-hidden p-5">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-pine via-emerald-400 to-coral" />
        <div className="rounded-[8px] border border-slate-100 bg-slate-50 p-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-slate-500">Agent workflow</p>
              <h2 className="mt-1 text-lg font-extrabold text-slate-950">Job readiness plan</h2>
            </div>
            <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-extrabold text-emerald-800">
              live
            </span>
          </div>
          <div className="mt-4 grid gap-2">
            {["Resume evidence", "Skill gap comparison", "30-day roadmap", "Project proof", "Interview stories"].map(
              (item, index) => (
                <div key={item} className="flex items-center gap-3 rounded-[8px] bg-white p-2.5 shadow-sm">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-pine text-[11px] font-extrabold text-white">
                    {index + 1}
                  </span>
                  <span className="text-xs font-bold text-slate-700">{item}</span>
                </div>
              ),
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
