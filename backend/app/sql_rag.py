"""SQL RAG over mediassist.db — a plain Python function with three explicit steps.

    1. NL -> SQL with the LLM (schema + real column values in the prompt)
    2. Clean the raw LLM output down to a single read-only SQL statement
    3. Execute it (read-only connection), then have the LLM phrase the result in natural language
"""

import logging
import re
import sqlite3
from functools import lru_cache

from app.config import get_settings
from app.llm import chat

log = logging.getLogger("medibot.sql")

MAX_ROWS = 200


class UnsafeSQLError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Schema context (introspected once from the DB, so the prompt matches reality)
# ---------------------------------------------------------------------------

_ENUM_COLUMNS = {
    "claims": ["department", "claim_type", "insurer", "status"],
    "maintenance_tickets": ["equipment_name", "category", "campus", "issue_type", "status"],
}
_DATE_COLUMNS = {
    "claims": ["submitted_date", "resolved_date"],
    "maintenance_tickets": ["raised_date", "resolved_date"],
}


def _connect() -> sqlite3.Connection:
    # mode=ro: the connection physically cannot write, whatever SQL the LLM produces
    return sqlite3.connect(f"file:{get_settings().db_path}?mode=ro", uri=True)


@lru_cache
def schema_context() -> str:
    parts = []
    with _connect() as conn:
        for table in _ENUM_COLUMNS:
            ddl = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()[0]
            parts.append(re.sub(r"\s+", " ", ddl))
            for col in _ENUM_COLUMNS[table]:
                vals = [r[0] for r in conn.execute(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL ORDER BY 1")]
                parts.append(f"  {table}.{col} values: {', '.join(map(repr, vals))}")
            for col in _DATE_COLUMNS[table]:
                lo, hi = conn.execute(f"SELECT MIN({col}), MAX({col}) FROM {table}").fetchone()
                parts.append(f"  {table}.{col}: TEXT 'YYYY-MM-DD', range {lo} .. {hi} (NULL if not yet resolved)")
    return "\n".join(parts)


@lru_cache
def _reference_date() -> str:
    """Latest date present in the data — used as 'today' for relative phrases like 'last month'."""
    with _connect() as conn:
        return conn.execute(
            "SELECT MAX(d) FROM (SELECT MAX(submitted_date) d FROM claims "
            "UNION ALL SELECT MAX(raised_date) FROM maintenance_tickets)"
        ).fetchone()[0]


# ---------------------------------------------------------------------------
# Step 1: NL -> SQL
# ---------------------------------------------------------------------------

SQL_SYSTEM = """You are an expert SQLite analyst for MediAssist Health Network.
Translate the user's question into ONE SQLite SELECT query over this schema:

{schema}

Rules:
- Output only the SQL query. No explanation, no markdown.
- Read-only: SELECT (or WITH ... SELECT) only.
- Use the exact categorical values listed above (lower-case, underscores), e.g. status = 'escalated'.
- Dates are TEXT 'YYYY-MM-DD'; use strftime / date() / substr for month and year logic.
- The dataset's reference "today" is {today}. Interpret relative periods ("last month", "this year",
  "recent") relative to that date, e.g. last month = the calendar month before {today}'s month.
- "Open" tickets means status IN ('open', 'in_progress', 'escalated') unless the user says status 'open' explicitly.
- Give aggregated columns readable aliases. Round money to 2 decimals.
- Add LIMIT {max_rows} if the query could return many rows."""


def generate_sql(question: str) -> str:
    system = SQL_SYSTEM.format(schema=schema_context(), today=_reference_date(), max_rows=MAX_ROWS)
    return chat(system, question)


# ---------------------------------------------------------------------------
# Step 2: clean raw LLM output -> a single safe SQL statement
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:sql|sqlite)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_START_RE = re.compile(r"\b(WITH|SELECT)\b", re.IGNORECASE)
_FORBIDDEN_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX|TRUNCATE)\b",
    re.IGNORECASE,
)


def extract_sql(raw: str) -> str:
    """Strip markdown fences / prose around the query and return exactly one SELECT statement."""
    text = raw.strip()
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    m = _START_RE.search(text)
    if not m:
        raise UnsafeSQLError(f"No SELECT statement found in LLM output: {raw[:200]!r}")
    text = text[m.start():]
    # keep only the first statement
    text = text.split(";")[0].strip()
    # drop trailing prose the model sometimes appends after a blank line
    text = re.split(r"\n\s*\n", text)[0].strip()
    if _FORBIDDEN_RE.search(text):
        raise UnsafeSQLError(f"Refusing non read-only SQL: {text!r}")
    return text


# ---------------------------------------------------------------------------
# Step 3: execute + phrase the answer
# ---------------------------------------------------------------------------

def run_sql(sql: str) -> tuple[list[str], list[tuple]]:
    with _connect() as conn:
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(MAX_ROWS)
    return cols, rows


ANSWER_SYSTEM = """You are MediBot, an analytics assistant for MediAssist Health Network.
Answer the user's question using ONLY the SQL result provided. Be concise and specific: state the
numbers, use ₹ for amounts with Indian digit grouping where natural, and present multiple rows as a
short markdown table or list. If the result is empty, say no matching records were found.
Do not mention SQL unless asked."""


def _format_rows(cols: list[str], rows: list[tuple]) -> str:
    if not rows:
        return "(no rows)"
    header = " | ".join(cols)
    body = "\n".join(" | ".join("" if v is None else str(v) for v in r) for r in rows)
    return f"{header}\n{body}"


def sql_rag_chain(question: str) -> str:
    """NL question -> SQL -> result -> natural-language answer."""
    answer, _ = sql_rag_chain_with_trace(question)
    return answer


def sql_rag_chain_with_trace(question: str) -> tuple[str, dict]:
    """Same as sql_rag_chain, but also returns the generated SQL and raw rows (for the API/debugging)."""
    raw = generate_sql(question)  # step 1
    sql = extract_sql(raw)  # step 2
    log.info("SQL for %r:\n%s", question, sql)
    try:
        cols, rows = run_sql(sql)  # step 3a
    except sqlite3.Error as e:
        # one self-repair attempt: show the model its error
        log.warning("SQL failed (%s), retrying", e)
        raw = generate_sql(f"{question}\n\nYour previous query failed.\nQuery: {sql}\nError: {e}\nWrite a corrected query.")
        sql = extract_sql(raw)
        cols, rows = run_sql(sql)
    result_text = _format_rows(cols, rows)
    answer = chat(ANSWER_SYSTEM, f"Question: {question}\n\nSQL result:\n{result_text}")  # step 3b
    return answer, {"sql": sql, "columns": cols, "row_count": len(rows)}
