from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment variables and `.env`.

    Field names map to env vars case-insensitively: `client_url` <- CLIENT_URL.
    Values are validated and converted to the annotated types at startup.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Document Matching Agent API"
    environment: Literal["development", "production", "test"] = "development"
    client_url: str = "http://localhost:5173"

    # postgresql+asyncpg:// = the PostgreSQL dialect through the async asyncpg driver
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/dma_py"
    database_echo: bool = False  # log every SQL statement (useful while learning)

    # JWT secrets must be at least 32 characters; tokens are stored in httpOnly cookies
    jwt_access_secret: str = Field(min_length=32)
    jwt_refresh_secret: str = Field(min_length=32)
    jwt_access_expires_minutes: int = 15
    jwt_refresh_expires_days: int = 7

    # Used by `python -m scripts.seed_super_admin`
    super_admin_username: str | None = None
    super_admin_password: str | None = Field(default=None, min_length=8)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Cached so the .env file is read once; call get_settings() wherever needed
@lru_cache
def get_settings() -> Settings:
    return Settings()
