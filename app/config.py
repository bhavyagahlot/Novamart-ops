import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    SYNAPSE_URL: str = "https://api.synapse.example.com"
    SYNAPSE_API_KEY: str = "syn_demo_key_123456789"
    SYNAPSE_PROJECT_ID: str = "novamart-ops-proj-001"
    REFUND_APPROVAL_LIMIT: float = 100.0
    DISCOUNT_APPROVAL_LIMIT_PERCENT: float = 15.0
    DATABASE_PATH: str = str(BASE_DIR / "novamart.db")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
