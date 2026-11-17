"use client";

import { FormEvent, useLayoutEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, saveSession } from "@/lib/api";
import { DEMO_USERS, ROLE_META } from "@/lib/roles";
import { CheckIcon, CrossIcon } from "@/components/Icons";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Next.js (cacheComponents) keeps this page mounted but hidden after we navigate to /chat.
  // Reset transient state when it is hidden, so returning here never shows a stuck
  // "Signing in…" button, disabled demo cards, or the previous user's password.
  useLayoutEffect(() => {
    return () => {
      setLoading(false);
      setPassword("");
      setError(null);
    };
  }, []);

  async function doLogin(u: string, p: string) {
    setLoading(true);
    setError(null);
    try {
      const session = await api.login(u, p);
      saveSession(session);
      router.push("/chat");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Login failed");
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    doLogin(username, password);
  }

  return (
    <main className="min-h-full flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-4xl grid md:grid-cols-2 gap-0 overflow-hidden rounded-2xl bg-white shadow-xl ring-1 ring-slate-200">
        {/* Brand panel */}
        <section className="bg-gradient-to-br from-teal-700 to-cyan-800 p-8 text-white flex flex-col">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-white/15">
              <CrossIcon className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-semibold leading-tight">MediBot</h1>
              <p className="text-sm text-teal-100">MediAssist Health Network</p>
            </div>
          </div>
          <p className="mt-8 text-teal-50 leading-relaxed">
            Ask questions about clinical protocols, nursing procedures, billing codes, equipment manuals and hospital
            policies — with cited answers drawn only from the documents your role is authorised to see.
          </p>
          <ul className="mt-6 space-y-2 text-sm text-teal-100">
            <li className="flex gap-2"><CheckIcon className="h-5 w-5 shrink-0" />Access control enforced in the vector database</li>
            <li className="flex gap-2"><CheckIcon className="h-5 w-5 shrink-0" />Hybrid search (semantic + BM25) with reranking</li>
            <li className="flex gap-2"><CheckIcon className="h-5 w-5 shrink-0" />Analytics over claims & maintenance data</li>
          </ul>
          <p className="mt-auto pt-8 text-xs text-teal-200">Internal use only · Demo environment</p>
        </section>

        {/* Form */}
        <section className="p-8">
          <h2 className="text-lg font-semibold">Sign in</h2>
          <form onSubmit={onSubmit} className="mt-5 space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-slate-700">Username</label>
              <input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
                placeholder="e.g. nurse.priya"
                required
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
                required
              />
            </div>
            {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-red-200">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-teal-700 px-4 py-2.5 font-medium text-white hover:bg-teal-800 disabled:opacity-60"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <div className="mt-8">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Demo accounts — click to sign in</h3>
            <div className="mt-3 grid gap-2">
              {DEMO_USERS.map((u) => {
                const meta = ROLE_META[u.role];
                return (
                  <button
                    key={u.username}
                    type="button"
                    disabled={loading}
                    onClick={() => doLogin(u.username, u.password)}
                    className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left hover:border-teal-500 hover:bg-teal-50/50 disabled:opacity-60"
                  >
                    <span>
                      <span className="block text-sm font-medium">{u.name}</span>
                      <span className="block font-mono text-xs text-slate-500">
                        {u.username} / {u.password}
                      </span>
                    </span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${meta.badge}`}>{meta.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
