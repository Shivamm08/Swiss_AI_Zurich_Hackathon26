from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Reads backend/.env or the repo-root .env (the one docker compose uses).
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Supabase: use the "Session pooler" URI from Project Settings -> Database.
    # postgres:// and postgresql:// URIs are accepted and converted below.
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:54322/triage"
    cors_origins: str = "http://localhost:5173"

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str | None = None
    azure_openai_embedding_deployment: str | None = None
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
    def llm_configured(self) -> bool:
        return bool(
            self.azure_openai_endpoint
            and self.azure_openai_api_key
            and self.azure_openai_chat_deployment
        )

    @property
    def embeddings_configured(self) -> bool:
        return bool(
            self.azure_openai_endpoint
            and self.azure_openai_api_key
            and self.azure_openai_embedding_deployment
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
