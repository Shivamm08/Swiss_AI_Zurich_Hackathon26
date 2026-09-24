from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProvider = Literal["azure", "openai", "none"]


class Settings(BaseSettings):
    # Reads backend/.env or the repo-root .env (the one docker compose uses).
    # Empty values (e.g. `LLM_TEMPERATURE=`) fall back to the defaults below.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore", env_ignore_empty=True)

    # Supabase: use the "Session pooler" URI from Project Settings -> Database.
    # postgres:// and postgresql:// URIs are accepted and converted below.
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:54322/triage"
    cors_origins: str = "http://localhost:5173"

    # LLM provider: Azure OpenAI wins if configured, otherwise OpenAI, otherwise heuristic mode.
    openai_api_key: str | None = None
    openai_chat_model: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str | None = None
    azure_openai_embedding_deployment: str | None = None

    # Apertus (Swiss open LLM) on Swisscom, an extra OpenAI-compatible provider offered next
    # to the main one. Only the key is required. Default URL is the Swiss {ai} Weeks hackathon
    # product (key from https://keymaker.ai-weeks.ch/); the public product uses
    # .../products/swiss-ai-platform/apertus-1.5-70b/v1 instead.
    apertus_api_key: str | None = None
    apertus_base_url: str = "https://api.swisscom.com/products/swiss-ai-weeks/apertus-1.5-70b/v1"
    apertus_model: str = "swiss-ai/Apertus-v1.5-70B"

    # Models offered in the UI's model picker (comma-separated ids / Azure deployments).
    # Unset = every chat model the OpenAI key can use (a long list).
    llm_model_choices: str | None = None

    # Unset = provider default (some reasoning models only accept the default).
    llm_temperature: float | None = None
    embedding_dim: int = 1536

    kb_dir: Path = Path(__file__).parent / "kb"

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_provider(self) -> LlmProvider:
        if self.azure_openai_endpoint and self.azure_openai_api_key:
            return "azure"
        if self.openai_api_key:
            return "openai"
        return "none"

    @property
    def model_choices(self) -> list[str]:
        if self.llm_provider == "none" or not self.llm_model_choices:
            return []
        return [m.strip() for m in self.llm_model_choices.split(",") if m.strip()]

    @property
    def chat_model(self) -> str | None:
        """Default model id (OpenAI) or deployment name (Azure) for chat calls:
        the configured one, else the first model in LLM_MODEL_CHOICES."""
        configured = {
            "azure": self.azure_openai_chat_deployment,
            "openai": self.openai_chat_model,
            "none": None,
        }[self.llm_provider]
        return configured or next(iter(self.model_choices), None)

    @property
    def embedding_model(self) -> str | None:
        return {
            "azure": self.azure_openai_embedding_deployment,
            "openai": self.openai_embedding_model,
            "none": None,
        }[self.llm_provider] or None

    @property
    def llm_configured(self) -> bool:
        return self.chat_model is not None

    @property
    def embeddings_configured(self) -> bool:
        return self.embedding_model is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
