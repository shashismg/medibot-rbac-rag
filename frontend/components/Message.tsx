"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatResponse, Source } from "@/lib/api";
import { COLLECTION_META } from "@/lib/roles";
import { DbIcon, DocIcon, ShieldIcon } from "./Icons";

export type ChatMessage =
  | { id: string; kind: "user"; text: string }
  | { id: string; kind: "bot"; data: ChatResponse }
  | { id: string; kind: "error"; text: string };

function RetrievalBadge({ type }: { type: ChatResponse["retrieval_type"] }) {
  const sql = type === "sql_rag";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ${
        sql ? "bg-indigo-50 text-indigo-700 ring-indigo-200" : "bg-teal-50 text-teal-700 ring-teal-200"
      }`}
    >
      {sql ? <DbIcon className="h-3.5 w-3.5" /> : <DocIcon className="h-3.5 w-3.5" />}
      {sql ? "SQL RAG" : "Hybrid RAG"}
    </span>
  );
}

function SourceList({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;
  return (
    <div className="mt-3 border-t border-slate-100 pt-3">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Sources</h4>
      <ol className="mt-2 space-y-1.5">
        {sources.map((s, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded bg-slate-100 text-[11px] font-semibold text-slate-600">
              {i + 1}
            </span>
            <span className="min-w-0">
              <span className="font-medium text-slate-800">{s.source_document}</span>
              <span className="text-slate-400"> · </span>
              <span className="text-slate-600">{s.section_title}</span>
              <span className="ml-2 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">
                {COLLECTION_META[s.collection]?.label ?? s.collection}
              </span>
              {s.chunk_type && s.chunk_type !== "text" && s.chunk_type !== "sql" && (
                <span className="ml-1 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-500">{s.chunk_type}</span>
              )}
              {typeof s.rerank_score === "number" && (
                <span className="ml-1 font-mono text-[11px] text-slate-400" title="Cross-encoder relevance score">
                  rel {s.rerank_score.toFixed(2)}
                </span>
              )}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function BotMessage({ data }: { data: ChatResponse }) {
  const [showSql, setShowSql] = useState(false);

  if (data.blocked) {
    return (
      <div className="rounded-2xl rounded-tl-sm border border-amber-200 bg-amber-50 p-4">
        <div className="flex items-center gap-2">
          <ShieldIcon className="h-5 w-5 text-amber-600" />
          <span className="text-sm font-semibold text-amber-800">Access restricted</span>
          <span className="ml-auto"><RetrievalBadge type={data.retrieval_type} /></span>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-amber-900">{data.answer}</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl rounded-tl-sm bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="mb-1 flex items-center gap-2">
        <RetrievalBadge type={data.retrieval_type} />
        {data.sql && (
          <button onClick={() => setShowSql((v) => !v)} className="text-xs text-indigo-600 hover:underline">
            {showSql ? "Hide SQL" : "Show SQL"}
          </button>
        )}
      </div>
      {showSql && data.sql && (
        <pre className="my-2 overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-slate-100">{data.sql}</pre>
      )}
      <div className="prose-answer text-[15px] leading-relaxed text-slate-800">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.answer}</ReactMarkdown>
      </div>
      <SourceList sources={data.sources} />
    </div>
  );
}
