from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "loomledger"
    environment: str = "local"
    db_path: str = "data/loomledger.sqlite"
    raw_dir: str = "data/raw"
    # PostgreSQL + pgvector
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "loomledger"
    postgres_user: str = "loomledger"
    postgres_password: str = ""
    # Gemini embeddings
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 3072

    gemini_api_key: str = ""
    llm_model: str = "gemini-3.5-flash-lite"
    llm_fallback_model: str = "gemini-3.1-flash-lite"
    gemini_input_price_per_million: float | None = None
    gemini_output_price_per_million: float | None = None

@lru_cache
def get_settings():
    return Settings()