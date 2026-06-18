"""LLM factory. Free Groq backend via LangChain, kept provider-agnostic.

The rest of the engine only ever calls ``get_llm()`` / ``get_structured_llm()``,
so swapping Groq for Gemini / a paid Claude key later is a one-file change.
"""

from dataclasses import dataclass
from typing import Any

from langchain_groq import ChatGroq

from engine.config import settings


FALLBACK_ERROR_MARKERS = (
    "rate limit",
    "too many requests",
    "quota",
    "exceeded",
    "exhausted",
    "organization has been restricted",
    "organization_restricted",
    "invalid api key",
    "authentication",
    "unauthorized",
    "forbidden",
    "connection error",
)


@dataclass
class FallbackChatGroq:
    """Tiny adapter that tries multiple Groq keys before failing.

    It intentionally exposes only the methods the engine uses: ``invoke``,
    ``bind``, and ``with_structured_output``.
    """

    clients: list[ChatGroq]
    labels: list[str]

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        errors: list[str] = []
        for idx, client in enumerate(self.clients):
            try:
                return client.invoke(*args, **kwargs)
            except Exception as exc:
                errors.append(f"{self.labels[idx]}: {exc}")
                if not _should_try_next_key(exc) or idx == len(self.clients) - 1:
                    raise RuntimeError(_fallback_error(errors)) from exc
        raise RuntimeError(_fallback_error(errors))

    def bind(self, **kwargs: Any) -> "FallbackChatGroq":
        return FallbackChatGroq(
            clients=[client.bind(**kwargs) for client in self.clients],
            labels=self.labels,
        )

    def with_structured_output(self, schema: Any) -> "FallbackChatGroq":
        return FallbackChatGroq(
            clients=[client.with_structured_output(schema) for client in self.clients],
            labels=self.labels,
        )


def get_llm(temperature: float | None = None, max_tokens: int = 1024) -> FallbackChatGroq:
    """Return a chat model. `max_tokens` is kept tight where possible because the
    Groq free tier counts requested output tokens against the per-minute budget."""
    keys = settings.groq_api_keys
    if not keys:
        raise RuntimeError(
            "No Groq API key is set. Add GROQ_API_KEY_1, GROQ_API_KEY_2, or "
            "GROQ_API_KEY_3 to .env."
        )

    return FallbackChatGroq(
        clients=[
            ChatGroq(
                model=settings.model,
                api_key=key,
                temperature=settings.temperature if temperature is None else temperature,
                max_tokens=max_tokens,
                max_retries=1,  # fallback across keys is faster than retrying one bad key
            )
            for key in keys
        ],
        labels=[f"GROQ_API_KEY_{idx}" for idx in range(1, len(keys) + 1)],
    )


def get_structured_llm(schema):
    """Return a model that emits a validated Pydantic object (for grading)."""
    # temperature 0 -> deterministic, structured feedback
    return get_llm(temperature=0).with_structured_output(schema)


def _should_try_next_key(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in FALLBACK_ERROR_MARKERS)


def _fallback_error(errors: list[str]) -> str:
    if not errors:
        return "All Groq API keys failed."
    return "All configured Groq API keys failed. " + " | ".join(errors)
