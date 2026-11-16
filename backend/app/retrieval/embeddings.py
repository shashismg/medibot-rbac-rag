"""Dense (semantic) + sparse (BM25) encoders, both via fastembed (ONNX, CPU-friendly)."""

from functools import lru_cache

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import models

from app.config import get_settings

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "bm25"


@lru_cache
def dense_model() -> TextEmbedding:
    return TextEmbedding(get_settings().dense_model)


@lru_cache
def sparse_model() -> SparseTextEmbedding:
    return SparseTextEmbedding(get_settings().sparse_model)


def embed_dense(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in dense_model().embed(texts, batch_size=32)]


def embed_dense_query(text: str) -> list[float]:
    # bge models expect a retrieval instruction prefix on queries; fastembed applies it in query_embed
    return next(iter(dense_model().query_embed(text))).tolist()


def embed_sparse(texts: list[str]) -> list[models.SparseVector]:
    return [
        models.SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
        for e in sparse_model().embed(texts, batch_size=32)
    ]


def embed_sparse_query(text: str) -> models.SparseVector:
    # BM25 query encoding: term presence only; IDF weighting is applied server-side (Modifier.IDF)
    e = next(iter(sparse_model().query_embed(text)))
    return models.SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
