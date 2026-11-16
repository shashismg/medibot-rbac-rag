"""Role-based access control: the single source of truth for who can see what.

The mapping here is used in two places:
  * at ingestion time, to stamp every chunk with its `access_roles` payload;
  * at query time, to build the Qdrant metadata filter (see retrieval/hybrid.py).
"""

from qdrant_client import models

ROLES = ("doctor", "nurse", "billing_executive", "technician", "admin")

COLLECTIONS = ("general", "clinical", "nursing", "billing", "equipment")

# collection -> roles allowed to retrieve its chunks
COLLECTION_ROLES: dict[str, list[str]] = {
    "general": list(ROLES),
    "clinical": ["doctor", "admin"],
    "nursing": ["nurse", "doctor", "admin"],
    "billing": ["billing_executive", "admin"],
    "equipment": ["technician", "admin"],
}

# Roles allowed to use SQL RAG (analytical questions over mediassist.db)
SQL_ROLES = {"billing_executive", "admin"}

ROLE_LABELS = {
    "doctor": "doctor",
    "nurse": "nurse",
    "billing_executive": "billing executive",
    "technician": "technician",
    "admin": "administrator",
}


def collections_for(role: str) -> list[str]:
    """Collections a role may access, in canonical order."""
    return [c for c in COLLECTIONS if role in COLLECTION_ROLES[c]]


def can_use_sql(role: str) -> bool:
    return role in SQL_ROLES


def role_filter(role: str) -> models.Filter:
    """Qdrant filter restricting results to chunks whose access_roles contains `role`.

    `access_roles` is a keyword-array payload; MatchValue on an array field matches
    when any element equals the value.
    """
    if role not in ROLES:
        raise ValueError(f"Unknown role: {role!r}")
    return models.Filter(
        must=[models.FieldCondition(key="access_roles", match=models.MatchValue(value=role))]
    )


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _article(word: str) -> str:
    return "an" if word[0] in "aeiou" else "a"


def refusal_message(role: str, blocked_collections: list[str]) -> str:
    label = ROLE_LABELS.get(role, role)
    allowed = _join(collections_for(role))
    blocked = _join(blocked_collections) if blocked_collections else "those"
    return (
        f"As {_article(label)} {label}, you don't have access to {blocked} documents. "
        f"I can only answer questions from the {allowed} collections."
    )


def sql_refusal_message(role: str) -> str:
    label = ROLE_LABELS.get(role, role)
    return (
        f"As {_article(label)} {label}, you don't have access to analytical queries over the "
        f"claims and maintenance-ticket database — that is limited to billing executives and "
        f"administrators. I can answer questions from the {_join(collections_for(role))} collections."
    )
