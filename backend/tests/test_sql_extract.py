import pytest

from app.sql_rag import UnsafeSQLError, extract_sql


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("SELECT COUNT(*) FROM claims", "SELECT COUNT(*) FROM claims"),
        ("```sql\nSELECT * FROM claims;\n```", "SELECT * FROM claims"),
        ("```\nSELECT 1\n```", "SELECT 1"),
        ("Here is the query:\n\nSELECT status, COUNT(*) FROM claims GROUP BY status;\n\nThis groups by status.",
         "SELECT status, COUNT(*) FROM claims GROUP BY status"),
        ("Sure! ```SQL\nWITH t AS (SELECT 1 x) SELECT x FROM t\n``` done", "WITH t AS (SELECT 1 x) SELECT x FROM t"),
        ("select a from b; select c from d", "select a from b"),
    ],
)
def test_extracts_single_select(raw, expected):
    assert extract_sql(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "DROP TABLE claims",
        "I cannot answer that.",
        "SELECT * FROM claims; DELETE FROM claims",  # second statement is discarded...
    ],
)
def test_rejects_or_neutralises_unsafe(raw):
    if raw.startswith("SELECT"):
        assert "DELETE" not in extract_sql(raw)
    else:
        with pytest.raises(UnsafeSQLError):
            extract_sql(raw)


def test_rejects_write_inside_select():
    with pytest.raises(UnsafeSQLError):
        extract_sql("WITH x AS (DELETE FROM claims RETURNING *) SELECT * FROM x")
