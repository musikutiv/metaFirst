"""Application configuration using Pydantic settings."""

from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Canonical DB path: supervisor/supervisor.db (relative to repo root)
# Computed as absolute path so it works regardless of cwd
_SUPERVISOR_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_DB_PATH = _SUPERVISOR_DIR / "supervisor.db"
_DEFAULT_DATABASE_URL = f"sqlite:///{_DEFAULT_DB_PATH}"


class Settings(BaseSettings):
    """Application settings."""

    # Database - defaults to supervisor/supervisor.db as absolute path
    database_url: str = _DEFAULT_DATABASE_URL

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Federated index
    federated_index_url: str = "http://localhost:8001"
    federated_index_timeout: int = 5

    # Environment
    supervisor_env: str = "development"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
