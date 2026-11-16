"""Thin wrapper over the Groq chat-completions API (cloud-hosted LLM inference)."""

from functools import lru_cache

from groq import Groq

from app.config import get_settings


@lru_cache
def get_client() -> Groq:
    s = get_settings()
    if not s.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set (see .env.example)")
    return Groq(api_key=s.groq_api_key)


def chat(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.0,
    json_mode: bool = False,
    max_tokens: int = 2048,
    reasoning_effort: str = "low",
) -> str:
    """Single-turn chat completion. gpt-oss models reason before answering; `low` keeps latency down
    and the reasoning trace is kept out of `content`."""
    kwargs: dict = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    model = model or get_settings().groq_model
    if "gpt-oss" in model:
        kwargs["reasoning_effort"] = reasoning_effort
        kwargs["include_reasoning"] = False
    resp = get_client().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return (resp.choices[0].message.content or "").strip()
