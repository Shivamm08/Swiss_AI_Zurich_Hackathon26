"""Thin LLM wrapper over OpenAI-compatible providers (same SDK, same calls).

- Main provider: Azure OpenAI or OpenAI, picked from .env (config.llm_provider).
- Extra provider: Apertus on Swisscom's Swiss AI Platform, when APERTUS_API_KEY is set.

Callers pass a `model` per request (chosen in the UI); the model id decides which
provider is called. Every function returns None when no model resolves, so the
pipeline falls back to its heuristic path and the app still runs without keys."""

import json
import re
from functools import lru_cache
from typing import Any, TypeVar

from openai import AzureOpenAI, OpenAI
from pydantic import BaseModel

from app.config import settings
from app.schemas import ModelOption, Provider

T = TypeVar("T", bound=BaseModel)


HEURISTIC = "heuristic"

# Chat-capable families from the OpenAI model list; excludes audio, image, realtime, etc.
_CHAT_MODEL = re.compile(r"^(gpt-|o\d)")
_NOT_CHAT = re.compile(r"(audio|realtime|transcribe|tts|image|search|instruct|codex|preview|live)")
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


@lru_cache
def get_client() -> OpenAI | None:
    """Client for the main provider (Azure OpenAI or OpenAI)."""
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
def get_apertus_client() -> OpenAI | None:
    if not settings.apertus_api_key:
        return None
    # Short timeout + one retry: a stuck upstream must not block triage for minutes.
    return OpenAI(api_key=settings.apertus_api_key, base_url=settings.apertus_base_url, timeout=60, max_retries=1)


def _main_models() -> list[str]:
    if settings.model_choices:
        return settings.model_choices
    if settings.llm_provider == "openai":
        ids = (m.id for m in get_client().models.list())
        return sorted(i for i in ids if _CHAT_MODEL.match(i) and not _NOT_CHAT.search(i))
    return [settings.chat_model] if settings.chat_model else []


@lru_cache
def available_models() -> tuple[ModelOption, ...]:
    """Models the UI may choose from. Cached for the life of the process."""
    choices: list[ModelOption] = []
    if settings.llm_provider != "none":
        choices += [ModelOption(id=m, label=m, provider=settings.llm_provider) for m in _main_models()]
    if settings.apertus_api_key:
        choices.append(ModelOption(id=settings.apertus_model, label="Apertus 1.5 70B (Swisscom)", provider="apertus"))
    return tuple(choices)


def available_model_ids() -> set[str]:
    return {m.id for m in available_models()}


def resolve_model(requested: str | None) -> str | None:
    """None = run the heuristic path. `requested` is validated by the API layer."""
    if requested == HEURISTIC:
        return None
    return requested or settings.chat_model


def model_name(model: str | None) -> str:
    return model or HEURISTIC


def _client_for(model: str) -> tuple[OpenAI | None, Provider | None]:
    if settings.apertus_api_key and model == settings.apertus_model:
        return get_apertus_client(), "apertus"
    return get_client(), (settings.llm_provider if settings.llm_provider != "none" else None)


def _chat_kwargs(model: str, system: str, user: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if settings.llm_temperature is not None:
        kwargs["temperature"] = settings.llm_temperature
    return kwargs


def _parse_via_prompt(client: OpenAI, model: str, system: str, user: str, schema: type[T]) -> T:
    """For providers without native structured outputs: ask for JSON, validate it ourselves."""
    instruction = (
        f"{system}\n\nRespond with ONLY a JSON object (no prose, no code fences) that matches this "
        f"JSON schema:\n{json.dumps(schema.model_json_schema())}"
    )
    content = client.chat.completions.create(**_chat_kwargs(model, instruction, user)).choices[0].message.content or ""
    match = _JSON_BLOCK.search(content)
    if not match:
        raise ValueError(f"{model} returned no JSON object")
    return schema.model_validate_json(match.group(0))


def parse(system: str, user: str, schema: type[T], model: str | None) -> T | None:
    """Structured output: the response is validated against `schema`."""
    if not model:
        return None
    client, provider = _client_for(model)
    if client is None:
        return None
    if provider == "apertus":
        # Swisscom's gateway times out on server-side JSON schemas (504); prompting for
        # JSON and validating it here returns in ~3s.
        return _parse_via_prompt(client, model, system, user, schema)
    completion = client.chat.completions.parse(**_chat_kwargs(model, system, user), response_format=schema)
    return completion.choices[0].message.parsed


def complete(system: str, user: str, model: str | None) -> str | None:
    if not model:
        return None
    client, _ = _client_for(model)
    if client is None:
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
