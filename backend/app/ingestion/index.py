"""Create the Qdrant collection (dense + BM25 sparse vectors) and upsert chunks."""

import uuid

from qdrant_client import models

from app.config import get_settings
from app.ingestion.chunk import Chunk
from app.retrieval.embeddings import DENSE_VECTOR, SPARSE_VECTOR, embed_dense, embed_sparse
from app.retrieval.qdrant import get_client

KEYWORD_INDEXES = ("access_roles", "collection", "source_document", "chunk_type")


def recreate_collection() -> None:
    s = get_settings()
    client = get_client()
    if client.collection_exists(s.qdrant_collection):
        client.delete_collection(s.qdrant_collection)
    client.create_collection(
        collection_name=s.qdrant_collection,
        vectors_config={
            DENSE_VECTOR: models.VectorParams(size=s.dense_dim, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            # IDF is computed by Qdrant over the stored corpus -> true BM25 scoring
            SPARSE_VECTOR: models.SparseVectorParams(modifier=models.Modifier.IDF)
        },
    )
    # Payload indexes make the RBAC filter cheap and are required for filtering in server mode at scale
    for field in KEYWORD_INDEXES:
        client.create_payload_index(
            s.qdrant_collection, field_name=field, field_schema=models.PayloadSchemaType.KEYWORD
        )


def _point_id(chunk: Chunk, i: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk.source_document}#{i}"))


def upsert_chunks(chunks: list[Chunk], batch_size: int = 64) -> int:
    s = get_settings()
    client = get_client()
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [c.text for c in batch]
        dense = embed_dense(texts)
        sparse = embed_sparse(texts)
        points = [
            models.PointStruct(
                id=_point_id(c, start + i),
                vector={DENSE_VECTOR: dense[i], SPARSE_VECTOR: sparse[i]},
                payload=c.payload(),
            )
            for i, c in enumerate(batch)
        ]
        client.upsert(s.qdrant_collection, points=points, wait=True)
    return len(chunks)
