"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, clearSession, CollectionsResponse, loadSession, Session } from "@/lib/api";
import { ALL_COLLECTIONS, COLLECTION_META, ROLE_META, SAMPLE_QUESTIONS } from "@/lib/roles";
import { BotMessage, ChatMessage } from "@/components/Message";
import { CheckIcon, CrossIcon, DbIcon, LockIcon, LogoutIcon, SendIcon } from "@/components/Icons";

let idCounter = 0;
const nextId = () => `m${++idCounter}`;

export default function ChatPage() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [access, setAccess] = useState<CollectionsResponse | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const s = loadSession();
    if (!s) {
      router.replace("/login");
      return;
    }
    setSession(s);
    api.collections(s.role).then(setAccess).catch(() => setAccess({ role: s.role, collections: s.collections, can_use_sql: false }));
  }, [router]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  function logout() {
    clearSession();
    router.replace("/login");
  }

  async function send(question: string) {
    if (!session || !question.trim() || busy) return;
    setMessages((m) => [...m, { id: nextId(), kind: "user", text: question }]);
    setInput("");
    setBusy(true);
    try {
      const data = await api.chat(question, session.access_token);
      setMessages((m) => [...m, { id: nextId(), kind: "bot", data }]);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        logout();
        return;
      }
      setMessages((m) => [...m, { id: nextId(), kind: "error", text: e instanceof Error ? e.message : "Request failed" }]);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }

  if (!session) return null;
  const meta = ROLE_META[session.role];
  const allowed = new Set(access?.collections ?? session.collections);

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="hidden w-72 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-teal-700 text-white">
            <CrossIcon className="h-5 w-5" />
          </div>
          <div>
            <div className="font-semibold leading-tight">MediBot</div>
            <div className="text-xs text-slate-500">MediAssist Health Network</div>
          </div>
        </div>

        <div className="px-5 py-4">
          <div className="text-sm font-medium">{session.display_name}</div>
          <div className="font-mono text-xs text-slate-500">{session.username}</div>
          <span className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${meta.badge}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
            {meta.label} · {meta.department}
          </span>
        </div>

        <div className="px-5">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your document access</h3>
          <ul className="mt-2 space-y-1">
            {ALL_COLLECTIONS.map((c) => {
              const ok = allowed.has(c);
              return (
                <li
                  key={c}
                  className={`flex items-start gap-2 rounded-lg px-2 py-1.5 ${ok ? "" : "opacity-50"}`}
                  title={COLLECTION_META[c].description}
                >
                  {ok ? <CheckIcon className="mt-0.5 h-4 w-4 text-teal-600" /> : <LockIcon className="mt-0.5 h-4 w-4 text-slate-400" />}
                  <span>
                    <span className={`block text-sm ${ok ? "font-medium" : "line-through"}`}>{COLLECTION_META[c].label}</span>
                    <span className="block text-xs text-slate-500">{COLLECTION_META[c].description}</span>
                  </span>
                </li>
              );
            })}
            <li className={`flex items-start gap-2 rounded-lg px-2 py-1.5 ${access?.can_use_sql ? "" : "opacity-50"}`}>
              {access?.can_use_sql ? <DbIcon className="mt-0.5 h-4 w-4 text-indigo-600" /> : <LockIcon className="mt-0.5 h-4 w-4 text-slate-400" />}
              <span>
                <span className={`block text-sm ${access?.can_use_sql ? "font-medium" : "line-through"}`}>Analytics (SQL)</span>
                <span className="block text-xs text-slate-500">Claims & maintenance-ticket statistics</span>
              </span>
            </li>
          </ul>
        </div>

        <div className="mt-auto border-t border-slate-200 p-4">
          <button onClick={logout} className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100">
            <LogoutIcon className="h-4 w-4" /> Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex min-w-0 flex-1 flex-col">
        {/* Mobile header with role badge */}
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:hidden">
          <span className="font-semibold">MediBot</span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${meta.badge}`}>{meta.label}</span>
          <button onClick={logout} aria-label="Sign out"><LogoutIcon className="h-5 w-5 text-slate-500" /></button>
        </header>
        <div className="border-b border-slate-200 bg-white px-4 py-2 text-xs text-slate-500 md:hidden">
          Access: {[...allowed].map((c) => COLLECTION_META[c]?.label ?? c).join(", ")}
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-6">
            {messages.length === 0 && (
              <div className="mt-10 text-center">
                <h2 className="text-2xl font-semibold">Hello, {session.display_name.split(" ")[0] === "Dr." ? session.display_name : session.display_name.split(" ")[0]}</h2>
                <p className="mt-2 text-slate-500">
                  Ask about anything in your {[...allowed].join(", ")} collections{access?.can_use_sql ? ", or ask for claims / maintenance statistics" : ""}.
                </p>
                <div className="mx-auto mt-6 grid max-w-xl gap-2">
                  {SAMPLE_QUESTIONS[session.role].map((q) => (
                    <button
                      key={q}
                      onClick={() => send(q)}
                      className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 hover:border-teal-500 hover:bg-teal-50/40"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-5">
              {messages.map((m) =>
                m.kind === "user" ? (
                  <div key={m.id} className="flex justify-end">
                    <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-teal-700 px-4 py-2.5 text-[15px] text-white">{m.text}</div>
                  </div>
                ) : m.kind === "bot" ? (
                  <div key={m.id} className="max-w-[92%]">
                    <BotMessage data={m.data} />
                  </div>
                ) : (
                  <div key={m.id} className="max-w-[92%] rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
                    {m.text}
                  </div>
                ),
              )}
              {busy && (
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <span className="flex gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-teal-600 [animation-delay:-0.3s]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-teal-600 [animation-delay:-0.15s]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-teal-600" />
                  </span>
                  Searching your permitted documents…
                </div>
              )}
              <div ref={endRef} />
            </div>
          </div>
        </div>

        <form onSubmit={onSubmit} className="border-t border-slate-200 bg-white p-4">
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              rows={1}
              placeholder="Ask MediBot…"
              className="max-h-40 min-h-[44px] flex-1 resize-none rounded-xl border border-slate-300 px-4 py-2.5 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="grid h-11 w-11 place-items-center rounded-xl bg-teal-700 text-white hover:bg-teal-800 disabled:opacity-50"
              aria-label="Send"
            >
              <SendIcon className="h-5 w-5" />
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
