from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    display_name: str
    role: str
    collections: list[str]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    # Accepted for API compatibility but IGNORED: the role always comes from the verified token.
    role: str | None = None


class Source(BaseModel):
    source_document: str
    section_title: str
    collection: str
    chunk_type: str | None = None
    rerank_score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    retrieval_type: Literal["hybrid_rag", "sql_rag"]
    role: str
    blocked: bool = False  # True when the request was refused by RBAC
    accessible_collections: list[str] = []
    sql: str | None = None  # the executed query, for transparency (SQL RAG only)


class CollectionsResponse(BaseModel):
    role: str
    collections: list[str]
    can_use_sql: bool
