"""Thin LLM wrapper over OpenAI or Azure OpenAI (same SDK, same calls).

The provider is picked from .env (see config.llm_provider). Callers may pass a
`model` per request (chosen in the UI); otherwise the configured default is
used. Every function returns None when no model resolves, so the pipeline falls
back to its heuristic path and the app still runs end to end without keys."""

import re
from functools import lru_cache
from typing import Any, TypeVar

from openai import AzureOpenAI, OpenAI
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)

HEURISTIC = "heuristic"

# Chat-capable families from the OpenAI model list; excludes audio, image, realtime, etc.
_CHAT_MODEL = re.compile(r"^(gpt-|o\d)")
_NOT_CHAT = re.compile(r"(audio|realtime|transcribe|tts|image|search|instruct|codex|preview|live)")


@lru_cache
def get_client() -> OpenAI | None:
    if settings.llm_provider == "azure":
        return AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
    if settings.llm_provider == "openai":
        return OpenAI(api_key=settings.openai_api_key)
    return None


@lru_cache
def available_models() -> tuple[str, ...]:
    """Models the UI may choose from. Cached for the life of the process."""
    if settings.model_choices:
        return tuple(settings.model_choices)
    if settings.llm_provider == "openai":
        ids = (m.id for m in get_client().models.list())
        return tuple(sorted(i for i in ids if _CHAT_MODEL.match(i) and not _NOT_CHAT.search(i)))
    return (settings.chat_model,) if settings.chat_model else ()


def resolve_model(requested: str | None) -> str | None:
    """None = run the heuristic path. `requested` is validated by the API layer."""
    if requested == HEURISTIC:
        return None
    return requested or settings.chat_model


def model_name(model: str | None) -> str:
    return model or HEURISTIC


def _chat_kwargs(model: str, system: str, user: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if settings.llm_temperature is not None:
        kwargs["temperature"] = settings.llm_temperature
    return kwargs


def parse(system: str, user: str, schema: type[T], model: str | None) -> T | None:
    """Structured output: the response is validated against `schema`."""
    client = get_client()
    if client is None or not model:
        return None
    completion = client.chat.completions.parse(**_chat_kwargs(model, system, user), response_format=schema)
    return completion.choices[0].message.parsed


def complete(system: str, user: str, model: str | None) -> str | None:
    client = get_client()
    if client is None or not model:
        return None
    completion = client.chat.completions.create(**_chat_kwargs(model, system, user))
    return completion.choices[0].message.content


def embed(texts: list[str]) -> list[list[float]] | None:
    client = get_client()
    if client is None or not settings.embedding_model:
        return None
    kwargs: dict[str, Any] = {"model": settings.embedding_model, "input": texts}
    if settings.embedding_model.startswith("text-embedding-3"):
        kwargs["dimensions"] = settings.embedding_dim  # must match the pgvector column
    response = client.embeddings.create(**kwargs)
    return [item.embedding for item in response.data]
