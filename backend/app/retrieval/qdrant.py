"""Qdrant client factory: server mode when QDRANT_URL is set, embedded on-disk mode otherwise."""

import atexit
from functools import lru_cache

from qdrant_client import QdrantClient

from app.config import get_settings


@lru_cache
def get_client() -> QdrantClient:
    s = get_settings()
    if s.qdrant_url:
        return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key or None, timeout=60)
    s.qdrant_local_path.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(s.qdrant_local_path))
    atexit.register(client.close)  # release the embedded store's lock cleanly on exit
    return client
