import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash")
    SYNAPSE_URL: str = Field(default="http://localhost:9000")
    SYNAPSE_API_KEY: str = Field(default="")
    SYNAPSE_PROJECT_ID: str = Field(default="novamart-ops")
    REFUND_APPROVAL_LIMIT: float = Field(default=100.0)
    DISCOUNT_APPROVAL_LIMIT_PERCENT: float = Field(default=15.0)
    DATABASE_PATH: str = Field(default="novamart.db")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
