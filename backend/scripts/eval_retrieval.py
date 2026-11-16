"""Retrieval quality: dense-only vs BM25-only vs hybrid (RRF) vs hybrid + cross-encoder rerank.

A retrieved chunk counts as relevant when it comes from the expected document AND its
(heading-contextualised) text contains every expected needle. Queries mix exact-term lookups
(drug names, ICD codes, fault codes, model numbers) with paraphrased conceptual questions.

Usage (from backend/, API stopped if using embedded Qdrant):
    uv run python -m scripts.eval_retrieval [--verbose]
"""

import argparse
import logging

from app.retrieval.hybrid import RetrievedChunk, dense_search, hybrid_search, sparse_search
from app.retrieval.rerank import rerank

ROLE = "admin"  # evaluation runs over the whole corpus
K = 10

# (query, expected source_document, needles that must appear in the chunk text, kind)
EVAL_SET = [
    # --- exact terminology: drug names / ICD codes / fault codes / model numbers ---
    ("Piperacillin-Tazobactam standard dose", "drug_formulary.pdf", ["Piperacillin-Tazobactam", "Q8H"], "exact"),
    ("What does fault code F-09 mean?", "equipment_manual.pdf", ["F-09"], "exact"),
    ("E-12 on the BM-500", "equipment_manual.pdf", ["E-12"], "exact"),
    ("ICD-10 J18.9 antibiotic regimen", "treatment_protocols.pdf", ["Community-Acquired Pneumonia", "Regimen"], "exact"),
    ("package rate for I21.4", "billing_codes.pdf", ["I21.4"], "exact"),
    ("CURB-65 disposition", "treatment_protocols.pdf", ["CURB-65"], "exact"),
    ("Bowie-Dick test frequency SterilPro 3000", "equipment_manual.pdf", ["Bowie-Dick"], "exact"),
    ("CLABSI surveillance", "infection_control.pdf", ["CLABSI"], "exact"),
    ("RadiPro MX-150 kVp for chest", "equipment_manual.pdf", ["Technique chart"], "exact"),
    ("EQ-HYD-1042 asset tag format", "equipment_manual.pdf", ["EQ-CAMPUS"], "exact"),
    ("Braden Scale score threshold", "icu_nursing_procedures.pdf", ["Braden"], "exact"),
    ("LASA pairs Tall Man lettering", "drug_formulary.pdf", ["LASA"], "exact"),
    # --- conceptual / paraphrased ---
    ("what IV cannula gauge should be used for a baby under 5kg", "icu_nursing_procedures.pdf", ["Cannula sizing"], "concept"),
    ("a colleague was pricked by a used needle, what are the first steps", "infection_control.pdf", ["Needlestick"], "concept"),
    ("when should a patient whose sugar stays high on two tablets be sent to a specialist", "treatment_protocols.pdf", ["Referral criteria"], "concept"),
    ("the insurer denied our claim, how do we respond", "claim_submission_guide.md", ["Claim Rejection Response"], "concept"),
    ("how often should the dressing on a central line be changed", "icu_nursing_procedures.pdf", ["72 hours"], "concept"),
    ("which painkillers must be avoided in dengue", "treatment_protocols.pdf", ["Dengue", "NSAIDs"], "concept"),
    ("what should the pressure limit be on the pump for a vein line", "equipment_manual.pdf", ["Occlusion pressure"], "concept"),
    ("which colour bin do soiled dressings go in", "infection_control.pdf", ["Waste Segregation"], "concept"),
]


def _relevant(c: RetrievedChunk, doc: str, needles: list[str]) -> bool:
    text = c.text.lower()
    return c.source_document == doc and all(n.lower() in text for n in needles)


def _rank(results: list[RetrievedChunk], doc: str, needles: list[str]) -> int | None:
    for i, c in enumerate(results, 1):
        if _relevant(c, doc, needles):
            return i
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true", help="log reranker scores per query")
    args = ap.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.WARNING)
        logging.getLogger("medibot.rerank").setLevel(logging.INFO)

    methods = {
        "dense_only": lambda q: dense_search(q, ROLE, K),
        "bm25_only": lambda q: sparse_search(q, ROLE, K),
        "hybrid_rrf": lambda q: hybrid_search(q, ROLE, K),
        "hybrid+rerank": lambda q: rerank(q, hybrid_search(q, ROLE, K), top_n=K),
    }
    ranks: dict[str, list[tuple[str, int | None]]] = {m: [] for m in methods}

    print(f"{'query':62} " + " ".join(f"{m:>13}" for m in methods))
    for q, doc, needles, kind in EVAL_SET:
        row = []
        for m, fn in methods.items():
            r = _rank(fn(q), doc, needles)
            ranks[m].append((kind, r))
            row.append(f"{(r if r else '-'):>13}")
        print(f"{('[' + kind[0] + '] ' + q)[:62]:62} " + " ".join(row))

    def metrics(rs: list[int | None]) -> tuple[float, float, float]:
        n = len(rs)
        hit1 = sum(1 for r in rs if r == 1) / n
        hit3 = sum(1 for r in rs if r and r <= 3) / n
        mrr = sum(1 / r for r in rs if r) / n
        return hit1, hit3, mrr

    print("\nRank of first relevant chunk shown above ('-' = not in top-10). Hit@3 matters most: top-3 reaches the LLM.\n")
    print(f"| Method | Hit@1 | Hit@3 | MRR@10 | Hit@3 (exact-term) | Hit@3 (conceptual) |")
    print(f"|---|---|---|---|---|---|")
    for m in methods:
        h1, h3, mrr = metrics([r for _, r in ranks[m]])
        e3 = metrics([r for k, r in ranks[m] if k == "exact"])[1]
        c3 = metrics([r for k, r in ranks[m] if k == "concept"])[1]
        print(f"| {m} | {h1:.2f} | {h3:.2f} | {mrr:.3f} | {e3:.2f} | {c3:.2f} |")


if __name__ == "__main__":
    main()
