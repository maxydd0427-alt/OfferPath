export function LoadingState() {
  return (
    <div className="grid gap-4">
      {[0, 1, 2].map((item) => (
        <div key={item} className="card overflow-hidden p-5">
          <div className="h-4 w-40 animate-pulse rounded bg-slate-200" />
          <div className="mt-4 h-3 w-full animate-pulse rounded bg-slate-100" />
          <div className="mt-2 h-3 w-4/5 animate-pulse rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}
