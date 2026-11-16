"""MediBot FastAPI application.

Run (from backend/):  uv run uvicorn app.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from app.auth import CurrentUser, authenticate, create_token, get_current_user
from app.config import get_settings
from app.pipeline import answer_question
from app.rbac import ROLES, can_use_sql, collections_for
from app.retrieval.embeddings import dense_model, sparse_model
from app.retrieval.qdrant import get_client
from app.retrieval.rerank import get_reranker
from app.schemas import ChatRequest, ChatResponse, CollectionsResponse, LoginRequest, LoginResponse

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("medibot.api")
for noisy in ("httpx", "sentence_transformers", "huggingface_hub"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm up models once so the first /chat request isn't slow
    log.info("Loading embedding + reranker models...")
    dense_model(), sparse_model(), get_reranker(), get_client()
    log.info("MediBot ready.")
    yield


app = FastAPI(title="MediBot API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    s = get_settings()
    try:
        points = get_client().count(s.qdrant_collection, exact=True).count
        qdrant = "ok"
    except Exception as e:  # pragma: no cover
        points, qdrant = 0, f"error: {e}"
    return {
        "status": "ok" if qdrant == "ok" and points > 0 else "degraded",
        "qdrant": qdrant,
        "qdrant_mode": "server" if s.qdrant_url else "embedded",
        "indexed_chunks": points,
        "llm_model": s.groq_model,
        "llm_configured": bool(s.groq_api_key),
    }


@app.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    user = authenticate(body.username, body.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    return LoginResponse(
        access_token=create_token(user),
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        collections=collections_for(user.role),
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest, user: CurrentUser = Depends(get_current_user)) -> ChatResponse:
    if body.role and body.role != user.role:
        # Never trust a client-supplied role; log the attempt and continue with the token's role.
        log.warning("Role mismatch: token=%s body=%s user=%s — using token role", user.role, body.role, user.username)
    return await run_in_threadpool(answer_question, body.question, user.role)


@app.get("/collections/{role}", response_model=CollectionsResponse)
def collections(role: str) -> CollectionsResponse:
    if role not in ROLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown role '{role}'")
    return CollectionsResponse(role=role, collections=collections_for(role), can_use_sql=can_use_sql(role))
