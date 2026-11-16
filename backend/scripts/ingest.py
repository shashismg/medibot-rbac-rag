"""One-off ingestion: parse every document with Docling, chunk hierarchically, index into Qdrant.

Usage (from backend/):  uv run python -m scripts.ingest [--dump chunks.jsonl]
"""

import argparse
import json
import time
from collections import Counter

from app.config import get_settings
from app.ingestion.chunk import chunk_document
from app.ingestion.index import recreate_collection, upsert_chunks
from app.ingestion.parse import discover_sources, parse
from app.retrieval.qdrant import get_client


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", help="also write all chunks to this JSONL file for inspection")
    args = ap.parse_args()

    s = get_settings()
    print(f"Data dir : {s.data_path}")
    print(f"Qdrant   : {s.qdrant_url or f'embedded @ {s.qdrant_local_path}'}")
    recreate_collection()

    all_chunks = []
    for src in discover_sources(s.data_path):
        t0 = time.time()
        doc = parse(src.path)
        chunks = chunk_document(doc, src.path.name, src.collection)
        all_chunks.extend(chunks)
        types = dict(Counter(c.chunk_type for c in chunks))
        print(f"  [{src.collection:9}] {src.path.name:32} {len(chunks):3} chunks {types}  ({time.time() - t0:.1f}s)")

    n = upsert_chunks(all_chunks)
    count = get_client().count(s.qdrant_collection, exact=True).count
    print(f"\nIndexed {n} chunks (collection now holds {count} points).")
    print("By collection :", dict(Counter(c.collection for c in all_chunks)))
    print("By chunk_type :", dict(Counter(c.chunk_type for c in all_chunks)))

    if args.dump:
        with open(args.dump, "w") as f:
            for c in all_chunks:
                f.write(json.dumps(c.payload(), ensure_ascii=False) + "\n")
        print(f"Chunks dumped to {args.dump}")


if __name__ == "__main__":
    main()
