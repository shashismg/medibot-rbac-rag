"""SQL RAG on real analytical questions: the generated SQL's result must equal a hand-written
ground-truth query's result, and the natural-language answer must mention the key figure."""

import pytest

from app.sql_rag import run_sql, sql_rag_chain, sql_rag_chain_with_trace
from tests.conftest import requires_llm

pytestmark = requires_llm

CASES = [
    (
        "How many claims are currently escalated?",
        "SELECT COUNT(*) FROM claims WHERE status = 'escalated'",
    ),
    (
        "Which equipment category has the most open maintenance tickets (status open)?",
        "SELECT category, COUNT(*) FROM maintenance_tickets WHERE status = 'open' GROUP BY category ORDER BY 2 DESC LIMIT 1",
    ),
    (
        "What is the total approved amount for Star Health claims?",
        "SELECT ROUND(SUM(approved_amount), 2) FROM claims WHERE insurer = 'Star Health'",
    ),
    (
        "How many claims were rejected in each department?",
        "SELECT department, COUNT(*) FROM claims WHERE status = 'rejected' GROUP BY department",
    ),
    (
        "How many maintenance tickets were raised at each campus?",
        "SELECT campus, COUNT(*) FROM maintenance_tickets GROUP BY campus",
    ),
    (
        "How many claims were submitted in March 2024?",
        "SELECT COUNT(*) FROM claims WHERE submitted_date LIKE '2024-03-%'",
    ),
]


def _as_set(rows):
    return {tuple(round(v, 2) if isinstance(v, float) else v for v in r) for r in rows}


@pytest.mark.parametrize("question,truth_sql", CASES, ids=[c[0][:40] for c in CASES])
def test_sql_rag_matches_ground_truth(question, truth_sql):
    answer, trace = sql_rag_chain_with_trace(question)
    _, got = run_sql(trace["sql"])
    _, expected = run_sql(truth_sql)
    assert _as_set(got) == _as_set(expected), f"SQL: {trace['sql']}"
    # the headline number should appear in the prose answer (ignoring ₹ / digit-group separators)
    headline = expected[0][-1]
    plain = answer.replace(",", "").replace(" ", "").replace(" ", "")
    assert str(int(headline)) in plain, answer


def test_plain_function_signature():
    out = sql_rag_chain("How many claims are there in total?")
    assert isinstance(out, str) and "85" in out
