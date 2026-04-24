from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> app/core -> app -> backend
BACKEND_DIR: Path = Path(__file__).resolve().parent.parent.parent
ENV_FILE: Path = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_ENV: Literal["local", "staging", "production"] = "local"
    APP_URL: str = "http://localhost:8000"

    SECRET_KEY: SecretStr
    DATABASE_URL: str
    REDIS_URL: str

    SMS_PROVIDER: str = "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
