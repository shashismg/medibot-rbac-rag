"""Hybrid retrieval: dense + BM25 in ONE Qdrant Query-API call, fused server-side with RRF.

RBAC is enforced here, inside the query: the role filter is attached to every prefetch branch
*and* the fusion stage, so Qdrant never returns a chunk the role may not see. There is no
post-hoc filtering in application code.
"""

from dataclasses import dataclass

from qdrant_client import models

from app.config import get_settings
from app.rbac import role_filter
from app.retrieval.embeddings import (
    DENSE_VECTOR,
    SPARSE_VECTOR,
    embed_dense_query,
    embed_sparse_query,
)
from app.retrieval.qdrant import get_client


@dataclass
class RetrievedChunk:
    id: str
    text: str
    source_document: str
    collection: str
    section_title: str
    chunk_type: str
    access_roles: list[str]
    retrieval_score: float
    rerank_score: float | None = None

    @classmethod
    def from_point(cls, p: models.ScoredPoint) -> "RetrievedChunk":
        pl = p.payload or {}
        return cls(
            id=str(p.id),
            text=pl.get("text", ""),
            source_document=pl.get("source_document", ""),
            collection=pl.get("collection", ""),
            section_title=pl.get("section_title", ""),
            chunk_type=pl.get("chunk_type", "text"),
            access_roles=pl.get("access_roles", []),
            retrieval_score=p.score,
        )


def hybrid_search(query: str, role: str, top_k: int | None = None) -> list[RetrievedChunk]:
    """Dense + sparse prefetch, Reciprocal Rank Fusion, RBAC filter at every stage."""
    s = get_settings()
    top_k = top_k or s.retrieval_top_k
    rbac = role_filter(role)
    prefetch_limit = top_k * 3  # each branch contributes a wider pool before fusion

    result = get_client().query_points(
        collection_name=s.qdrant_collection,
        prefetch=[
            models.Prefetch(
                query=embed_dense_query(query),
                using=DENSE_VECTOR,
                filter=rbac,
                limit=prefetch_limit,
            ),
            models.Prefetch(
                query=embed_sparse_query(query),
                using=SPARSE_VECTOR,
                filter=rbac,
                limit=prefetch_limit,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        query_filter=rbac,
        limit=top_k,
        with_payload=True,
    )
    return [RetrievedChunk.from_point(p) for p in result.points]


def dense_search(query: str, role: str, top_k: int | None = None) -> list[RetrievedChunk]:
    """Dense-only baseline (same RBAC filter), used for evaluation comparisons."""
    s = get_settings()
    result = get_client().query_points(
        collection_name=s.qdrant_collection,
        query=embed_dense_query(query),
        using=DENSE_VECTOR,
        query_filter=role_filter(role),
        limit=top_k or s.retrieval_top_k,
        with_payload=True,
    )
    return [RetrievedChunk.from_point(p) for p in result.points]


def sparse_search(query: str, role: str, top_k: int | None = None) -> list[RetrievedChunk]:
    """BM25-only baseline (same RBAC filter), used for evaluation comparisons."""
    s = get_settings()
    result = get_client().query_points(
        collection_name=s.qdrant_collection,
        query=embed_sparse_query(query),
        using=SPARSE_VECTOR,
        query_filter=role_filter(role),
        limit=top_k or s.retrieval_top_k,
        with_payload=True,
    )
    return [RetrievedChunk.from_point(p) for p in result.points]
