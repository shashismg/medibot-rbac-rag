"""Cross-encoder reranking: score (query, chunk) pairs jointly and keep only the top-N."""

import logging
from functools import lru_cache

from sentence_transformers import CrossEncoder

from app.config import get_settings
from app.retrieval.hybrid import RetrievedChunk

log = logging.getLogger("medibot.rerank")


@lru_cache
def get_reranker() -> CrossEncoder:
    return CrossEncoder(get_settings().reranker_model)


def rerank(query: str, candidates: list[RetrievedChunk], top_n: int | None = None) -> list[RetrievedChunk]:
    if not candidates:
        return []
    top_n = top_n or get_settings().rerank_top_n
    scores = get_reranker().predict([(query, c.text) for c in candidates])
    for c, sc in zip(candidates, scores, strict=True):
        c.rerank_score = float(sc)

    ranked = sorted(candidates, key=lambda c: c.rerank_score, reverse=True)
    if log.isEnabledFor(logging.INFO):
        lines = [
            f"  hybrid#{candidates.index(c) + 1:<2} -> rerank#{i + 1:<2} score={c.rerank_score:7.3f}  "
            f"{c.source_document} :: {c.section_title}"
            for i, c in enumerate(ranked)
        ]
        log.info("Rerank for %r\n%s", query, "\n".join(lines))
    return ranked[:top_n]
