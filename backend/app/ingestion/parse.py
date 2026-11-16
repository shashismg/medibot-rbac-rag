"""Structure-aware parsing with Docling (PDF + Markdown -> DoclingDocument)."""

import re
from collections.abc import Iterator
from io import BytesIO
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import DoclingDocument, SectionHeaderItem

from app.rbac import COLLECTIONS

SUPPORTED_SUFFIXES = {".pdf", ".md"}


@dataclass
class SourceFile:
    path: Path
    collection: str


@lru_cache
def get_converter() -> DocumentConverter:
    pdf_opts = PdfPipelineOptions()
    pdf_opts.do_ocr = False  # PDFs are digital; OCR only slows things down
    pdf_opts.do_table_structure = True  # recover table rows/columns (drug formulary, billing codes)
    pdf_opts.table_structure_options.mode = TableFormerMode.ACCURATE
    pdf_opts.table_structure_options.do_cell_matching = True
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.MD],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts)},
    )


def discover_sources(data_dir: Path) -> Iterator[SourceFile]:
    """Each top-level folder in data_dir is a collection (general, clinical, ...)."""
    for collection in COLLECTIONS:
        folder = data_dir / collection
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() in SUPPORTED_SUFFIXES:
                yield SourceFile(path=path, collection=collection)


_FENCE = re.compile(r"^```.*?^```[ \t]*$", re.MULTILINE | re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*([^*]+?)\*\*")


def clean_markdown(text: str) -> str:
    """Drop inline emphasis / inline-code markers outside fenced blocks.

    Docling models inline formatting as separate inline items, which the chunker would emit on
    separate lines (and misclassify prose as `code`). Fenced code blocks are kept intact.
    """
    out, last = [], 0
    for m in _FENCE.finditer(text):
        prose = text[last : m.start()]
        out.append(_BOLD.sub(r"\1", _INLINE_CODE.sub(r"\1", prose)))
        out.append(m.group(0))
        last = m.end()
    tail = text[last:]
    out.append(_BOLD.sub(r"\1", _INLINE_CODE.sub(r"\1", tail)))
    return "".join(out)


_SECTION_PATTERN = re.compile(r"^(\d+\.\s|[A-Z]\.\s|SOP\s+\d+|Appendix\b|Disclaimer\b)")
_FAQ_PATTERN = re.compile(r"^Q\d+\.\s")


def infer_pdf_heading_levels(doc: DoclingDocument) -> None:
    """Rebuild the heading hierarchy that PDF layout analysis flattens.

    Docling's PDF pipeline reports every section header at level 1, so a sub-heading such as
    "Fault codes" loses its parent "B. Infusion Pump - DriveFlow IP-200". MediAssist documents use
    a consistent numbering convention, which we use to re-assign levels:
      level 1  first header (document title)
      level 2  numbered / lettered sections ("3. ...", "B. ...", "SOP 4 - ...", "Appendix ...")
               — or, in FAQ documents, the topic headers above the "Qn." questions
      level 3  everything else (sub-sections such as "Monitoring", "Fault codes", "Qn. ...")
    HybridChunker uses these levels to build each chunk's heading path.
    """
    headers = [
        item
        for item, _ in doc.iterate_items()
        if isinstance(item, SectionHeaderItem)
    ]
    if not headers:
        return
    is_faq = any(_FAQ_PATTERN.match(h.text) for h in headers)
    for i, h in enumerate(headers):
        text = h.text.strip()
        if i == 0:
            h.level = 1
        elif _SECTION_PATTERN.match(text) or (is_faq and not _FAQ_PATTERN.match(text)):
            h.level = 2
        else:
            h.level = 3


def parse(path: Path) -> DoclingDocument:
    converter = get_converter()
    if path.suffix.lower() == ".md":
        # Markdown already carries explicit #/##/### levels
        cleaned = clean_markdown(path.read_text(encoding="utf-8"))
        stream = DocumentStream(name=path.name, stream=BytesIO(cleaned.encode("utf-8")))
        return converter.convert(stream).document
    doc = converter.convert(path).document
    infer_pdf_heading_levels(doc)
    return doc
