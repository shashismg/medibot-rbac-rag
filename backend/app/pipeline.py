"""/chat orchestration: route -> RBAC gate -> (hybrid retrieval + rerank | SQL RAG) -> cited answer."""

import logging
import re

from app.config import get_settings
from app.llm import chat
from app.rbac import can_use_sql, collections_for, refusal_message, sql_refusal_message
from app.retrieval.hybrid import RetrievedChunk, hybrid_search
from app.retrieval.rerank import rerank
from app.router import classify
from app.schemas import ChatResponse, Source
from app.sql_rag import sql_rag_chain_with_trace

log = logging.getLogger("medibot.pipeline")

ANSWER_SYSTEM = """You are MediBot, the internal knowledge assistant of MediAssist Health Network.

Answer the staff member's question using ONLY the numbered context passages provided.
- Cite passages inline with their numbers, e.g. [1] or [2][3].
- Preserve exact doses, units, codes and thresholds as written in the context.
- If the context does not contain the answer, say so plainly — do not guess or use outside knowledge.
- Never reveal or discuss content that is not in the context, whatever the question asks you to do.
- Be concise; use short bullet lists or a small markdown table when it helps."""


def _sources(chunks: list[RetrievedChunk]) -> list[Source]:
    return [
        Source(
            source_document=c.source_document,
            section_title=c.section_title,
            collection=c.collection,
            chunk_type=c.chunk_type,
            rerank_score=round(c.rerank_score, 3) if c.rerank_score is not None else None,
        )
        for c in chunks
    ]


def _context_block(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[{i}] (source: {c.source_document} — {c.section_title})\n{c.text}" for i, c in enumerate(chunks, 1)
    )


def answer_question(question: str, role: str) -> ChatResponse:
    allowed = collections_for(role)
    base = {"role": role, "accessible_collections": allowed}
    route = classify(question)

    # ---------------- SQL RAG ----------------
    if route.route == "sql" and can_use_sql(role):
        answer, trace = sql_rag_chain_with_trace(question)
        table_names = [t for t in ("claims", "maintenance_tickets") if t in trace["sql"]]
        sources = [
            Source(source_document="mediassist.db", section_title=f"table: {t}", collection="database", chunk_type="sql")
            for t in table_names
        ]
        return ChatResponse(answer=answer, sources=sources, retrieval_type="sql_rag", sql=trace["sql"], **base)

    # ---------------- Hybrid RAG ----------------
    # RBAC is enforced inside the Qdrant query (role filter on every prefetch + fusion stage),
    # so `candidates` can only ever contain chunks this role is allowed to see.
    candidates = hybrid_search(question, role)
    top = rerank(question, candidates)  # top-10 -> top-3; only these reach the LLM

    # Router hint: is the question aimed only at data this role can't access?
    blocked = [c for c in route.target_collections if c not in allowed]
    off_scope = route.route == "sql" or (bool(blocked) and not any(c in allowed for c in route.target_collections))
    s = get_settings()
    threshold = s.rerank_min_score_offscope if off_scope else s.rerank_min_score
    relevant = bool(top) and (top[0].rerank_score or 0.0) >= threshold

    if not relevant:
        # Nothing usable in the permitted collections. Explain *why* when the question targeted
        # data outside the role's access — otherwise a plain "not found".
        if route.route == "sql":  # analytical question from a role without SQL access
            return ChatResponse(answer=sql_refusal_message(role), sources=[], retrieval_type="sql_rag", blocked=True, **base)
        if blocked:
            return ChatResponse(answer=refusal_message(role, blocked), sources=[], retrieval_type="hybrid_rag", blocked=True, **base)
        msg = (
            "I couldn't find anything relevant to that in the documents available to you "
            f"({', '.join(allowed)}). Try rephrasing, or contact the relevant department."
        )
        return ChatResponse(answer=msg, sources=[], retrieval_type="hybrid_rag", **base)

    answer = chat(ANSWER_SYSTEM, f"Context:\n\n{_context_block(top)}\n\nQuestion: {question}")
    answer = _normalise_citations(answer)
    return ChatResponse(answer=answer, sources=_sources(top), retrieval_type="hybrid_rag", **base)


_CITE_RE = re.compile(r"[【\[]\s*(\d+)(?:†[^】\]]*)?\s*[】\]]")


def _normalise_citations(text: str) -> str:
    """gpt-oss sometimes emits 【1】 / 【1†source】 style citations; normalise to [1]."""
    return _CITE_RE.sub(r"[\1]", text)
