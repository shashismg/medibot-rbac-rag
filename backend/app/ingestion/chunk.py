"""Hierarchical, token-aware chunking with Docling's HybridChunker.

Pass 1 (hierarchical): split along the document tree — section -> subsection -> paragraph/table.
Pass 2 (token-aware): split oversized chunks and merge undersized peers under the same headings,
bounded by the embedding model's tokenizer.

Each chunk's *embedded* text is `chunker.contextualize(chunk)`, which prefixes the heading path,
so "25mg twice daily" is stored as "Drug Formulary > Antihypertensives > Amlodipine\n25mg twice daily".
"""

from dataclasses import dataclass, field
from functools import lru_cache

from docling.chunking import HybridChunker
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.transforms.serializer.markdown import MarkdownTableSerializer
from docling_core.types.doc import DocItemLabel, DoclingDocument

from app.config import get_settings
from app.rbac import COLLECTION_ROLES


@dataclass
class Chunk:
    text: str  # heading-contextualised text (what gets embedded and shown to the LLM)
    source_document: str
    collection: str
    access_roles: list[str]
    section_title: str
    chunk_type: str  # text | table | heading | code
    headings: list[str] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)

    def payload(self) -> dict:
        return {
            "text": self.text,
            "source_document": self.source_document,
            "collection": self.collection,
            "access_roles": self.access_roles,
            "section_title": self.section_title,
            "chunk_type": self.chunk_type,
            "headings": self.headings,
            "page_numbers": self.page_numbers,
        }


class MarkdownTableSerializerProvider(ChunkingSerializerProvider):
    """Serialize tables as Markdown (header row preserved) instead of flattened triplets,
    so dosage / billing-code tables stay readable for both the embedder and the LLM."""

    def get_serializer(self, doc: DoclingDocument) -> ChunkingDocSerializer:
        return ChunkingDocSerializer(doc=doc, table_serializer=MarkdownTableSerializer())


@lru_cache
def get_chunker() -> HybridChunker:
    s = get_settings()
    tokenizer = HuggingFaceTokenizer.from_pretrained(s.chunk_tokenizer, max_tokens=s.chunk_max_tokens)
    return HybridChunker(
        tokenizer=tokenizer,
        merge_peers=True,
        repeat_table_header=True,  # an oversized table split in two keeps its header row in both
        serializer_provider=MarkdownTableSerializerProvider(),
    )


_HEADING_LABELS = {DocItemLabel.SECTION_HEADER, DocItemLabel.TITLE}


def _chunk_type(doc_items) -> str:
    labels = {item.label for item in doc_items}
    if DocItemLabel.TABLE in labels:
        return "table"
    if DocItemLabel.CODE in labels:
        return "code"
    if labels and labels <= _HEADING_LABELS:
        return "heading"
    return "text"


def _pages(doc_items) -> list[int]:
    pages = {prov.page_no for item in doc_items for prov in (getattr(item, "prov", None) or [])}
    return sorted(pages)


def chunk_document(doc: DoclingDocument, source_document: str, collection: str) -> list[Chunk]:
    chunker = get_chunker()
    roles = COLLECTION_ROLES[collection]
    doc_title = doc.name or source_document
    out: list[Chunk] = []
    for raw in chunker.chunk(dl_doc=doc):
        text = chunker.contextualize(chunk=raw).strip()
        if not text:
            continue
        headings = list(raw.meta.headings or [])
        out.append(
            Chunk(
                text=text,
                source_document=source_document,
                collection=collection,
                access_roles=list(roles),
                section_title=headings[-1] if headings else doc_title,
                chunk_type=_chunk_type(raw.meta.doc_items),
                headings=headings,
                page_numbers=_pages(raw.meta.doc_items),
            )
        )
    return out
