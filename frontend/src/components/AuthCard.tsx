import { FormEvent, useState } from "react";
import type { User } from "../types/analysis";

type AuthCardProps = {
  user: User | null;
  busy: boolean;
  error: string;
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string) => Promise<void>;
  onLogout: () => void;
};

export function AuthCard({ user, busy, error, onLogin, onRegister, onLogout }: AuthCardProps) {
  const [email, setEmail] = useState("max@example.com");
  const [password, setPassword] = useState("strong-password");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onLogin(email, password);
  }

  if (user) {
    return (
      <section className="card p-5">
        <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-pine">Signed in</p>
        <h2 className="mt-2 text-lg font-extrabold text-slate-950">{user.email}</h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">Your session token is stored locally for API calls.</p>
        <button className="secondary-button mt-5 w-full" type="button" onClick={onLogout}>
          Sign out
        </button>
      </section>
    );
  }

  return (
      <section className="card p-5">
      <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-pine">Account</p>
      <h2 className="mt-2 text-lg font-extrabold text-slate-950">Login or register</h2>
      <form className="mt-4 grid gap-3" onSubmit={submit}>
        <label className="label">
          Email
          <input className="field" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label className="label">
          Password
          <input
            className="field"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error ? <p className="rounded-[8px] bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
        <div className="grid gap-3 sm:grid-cols-2">
          <button className="secondary-button" type="button" disabled={busy} onClick={() => onRegister(email, password)}>
            Register
          </button>
          <button className="primary-button" type="submit" disabled={busy}>
            Login
          </button>
        </div>
      </form>
    </section>
  );
}
