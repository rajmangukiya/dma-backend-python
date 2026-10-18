from functools import lru_cache
from typing import Literal

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

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Cached so the .env file is read once; call get_settings() wherever needed
@lru_cache
def get_settings() -> Settings:
    return Settings()
