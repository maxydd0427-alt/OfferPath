import type { ReactNode } from "react";
import type { User } from "../types/analysis";
import { api } from "../lib/api";

type ShellProps = {
  user: User | null;
  children: ReactNode;
};

export function Shell({ user, children }: ShellProps) {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-[8px] bg-pine text-xs font-extrabold text-white shadow-lg">
            OP
          </div>
          <div>
            <p className="text-sm font-extrabold text-slate-950">OfferPath</p>
            <p className="text-xs text-slate-500">{api.baseUrl}</p>
          </div>
        </div>
        <div className="hidden rounded-full border border-white/80 bg-white/70 px-4 py-2 text-sm font-bold text-slate-600 shadow-sm sm:block">
          {user ? user.email : "Career demo"}
        </div>
      </header>
      <main className="mx-auto grid w-full max-w-6xl gap-6 px-4 pb-10 sm:px-6">{children}</main>
    </div>
  );
}
