export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Role = "doctor" | "nurse" | "billing_executive" | "technician" | "admin";

export interface Session {
  access_token: string;
  username: string;
  display_name: string;
  role: Role;
  collections: string[];
}

export interface Source {
  source_document: string;
  section_title: string;
  collection: string;
  chunk_type?: string | null;
  rerank_score?: number | null;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  retrieval_type: "hybrid_rag" | "sql_rag";
  role: Role;
  blocked: boolean;
  accessible_collections: string[];
  sql?: string | null;
}

export interface CollectionsResponse {
  role: Role;
  collections: string[];
  can_use_sql: boolean;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers: { ...headers, ...(init.headers as object) } });
  } catch {
    throw new ApiError(0, `Cannot reach the MediBot API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  login: (username: string, password: string) =>
    request<Session>("/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  chat: (question: string, token: string) =>
    request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify({ question }) }, token),
  collections: (role: Role) => request<CollectionsResponse>(`/collections/${role}`),
};

// ---- session persistence (per-browser convenience) ----
const KEY = "medibot.session";

export function saveSession(s: Session) {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {}
}

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(KEY);
  } catch {}
}
