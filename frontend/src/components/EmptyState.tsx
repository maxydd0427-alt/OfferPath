type EmptyStateProps = {
  title: string;
  message: string;
};

export function EmptyState({ title, message }: EmptyStateProps) {
  return (
    <div className="card grid min-h-44 place-items-center p-8 text-center">
      <div>
        <p className="text-sm font-extrabold uppercase tracking-[0.18em] text-pine">OfferPath</p>
        <h3 className="mt-2 text-xl font-extrabold text-slate-950">{title}</h3>
        <p className="mt-2 max-w-md text-sm leading-6 text-slate-600">{message}</p>
      </div>
    </div>
  );
}
