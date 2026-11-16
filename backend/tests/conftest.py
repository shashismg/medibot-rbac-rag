import os

import pytest

from app.config import get_settings


def _qdrant_ready() -> bool:
    try:
        from app.retrieval.qdrant import get_client

        s = get_settings()
        return get_client().collection_exists(s.qdrant_collection)
    except Exception:  # e.g. embedded store locked by a running API, or server down
        return False


requires_index = pytest.mark.skipif(
    not _qdrant_ready(), reason="Qdrant index not available (run scripts.ingest; stop the API if using embedded mode)"
)
requires_llm = pytest.mark.skipif(not (get_settings().groq_api_key or os.getenv("GROQ_API_KEY")), reason="GROQ_API_KEY not set")
