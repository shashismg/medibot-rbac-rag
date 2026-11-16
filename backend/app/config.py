"""Central configuration, loaded from environment / .env (repo root or backend/)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    # LLM
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_router_model: str = "openai/gpt-oss-20b"  # small/fast model for query routing

    # Qdrant
    qdrant_url: str = ""  # empty -> embedded mode
    qdrant_api_key: str = ""
    qdrant_path: str = "./qdrant_local"
    qdrant_collection: str = "medibot_docs"

    # Models
    dense_model: str = "BAAI/bge-small-en-v1.5"
    dense_dim: int = 384
    sparse_model: str = "Qdrant/bm25"
    reranker_model: str = "mixedbread-ai/mxbai-rerank-base-v1"
    chunk_tokenizer: str = "BAAI/bge-small-en-v1.5"
    chunk_max_tokens: int = 512

    # Retrieval
    retrieval_top_k: int = 10  # broad candidate set from hybrid search
    rerank_top_n: int = 3  # chunks passed to the LLM
    # mxbai reranker outputs a 0..1 relevance probability. If the best chunk scores below the
    # threshold, we treat it as "nothing relevant in your collections". The bar is higher when the
    # router says the question targets only collections the role cannot access.
    rerank_min_score: float = 0.01
    rerank_min_score_offscope: float = 0.10

    # Auth
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # Data
    data_dir: str = "../Medibot_Assignment_Resources/mediassist_data"

    def _resolve(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def data_path(self) -> Path:
        return self._resolve(self.data_dir)

    @property
    def db_path(self) -> Path:
        return self.data_path / "db" / "mediassist.db"

    @property
    def qdrant_local_path(self) -> Path:
        return self._resolve(self.qdrant_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
