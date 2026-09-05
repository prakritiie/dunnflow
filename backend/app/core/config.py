from __future__ import annotations
import pathlib
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://dunnflow:dunnflow@127.0.0.1:5432/dunnflow"
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    DUNNFLOW_ENV: str = "local"
    DUNNFLOW_API_TOKEN: str = ""
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8443,http://127.0.0.1:8443"
    CONFIG_DIR: str = str(pathlib.Path(__file__).resolve().parents[2] / "config")
    DEFAULT_SEED: int = 42
    DEFAULT_N: int = 400
    LLM_MODE: str = "STUB"
    LLM_PROVIDER: str = "openai"        # openai | gemini
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str = ""
    LLM_TIMEOUT_MS: int = 8000
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    PSP_MODE: str = "MOCK"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    RATE_LIMIT_WRITES_PER_MIN: int = 30
    LOG_LEVEL: str = "INFO"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def auth_enabled(self) -> bool:
        return bool(self.DUNNFLOW_API_TOKEN)


settings = Settings()
