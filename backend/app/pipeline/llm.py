"""Thin Azure OpenAI wrapper. Every function returns None when Azure is not
configured, so the pipeline falls back to its heuristic path and the app still
runs end to end without keys."""

from functools import lru_cache
from typing import TypeVar

from openai import AzureOpenAI
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)


@lru_cache
def get_client() -> AzureOpenAI | None:
    if not (settings.azure_openai_endpoint and settings.azure_openai_api_key):
        return None
    return AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )


def model_name() -> str:
    return settings.azure_openai_chat_deployment if settings.llm_configured else "heuristic"


def parse(system: str, user: str, schema: type[T]) -> T | None:
    """Structured output: the response is validated against `schema`."""
    client = get_client()
    if client is None or not settings.azure_openai_chat_deployment:
        return None
    completion = client.chat.completions.parse(
        model=settings.azure_openai_chat_deployment,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format=schema,
        temperature=0,
    )
    return completion.choices[0].message.parsed


def complete(system: str, user: str) -> str | None:
    client = get_client()
    if client is None or not settings.azure_openai_chat_deployment:
        return None
    completion = client.chat.completions.create(
        model=settings.azure_openai_chat_deployment,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
    )
    return completion.choices[0].message.content


def embed(texts: list[str]) -> list[list[float]] | None:
    client = get_client()
    if client is None or not settings.azure_openai_embedding_deployment:
        return None
    response = client.embeddings.create(model=settings.azure_openai_embedding_deployment, input=texts)
    return [item.embedding for item in response.data]
