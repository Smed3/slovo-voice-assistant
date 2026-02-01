"""
Configuration management for Slovo Agent Runtime.
"""

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    # Application
    version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = Field(default="127.0.0.1", alias="AGENT_HOST")
    port: int = Field(default=8741, alias="AGENT_PORT")
    secret_key: str = Field(
        default="dev-secret-key-change-in-production", alias="AGENT_SECRET_KEY"
    )

    # LLM Providers
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")

    # LLM Configuration
    llm_provider: Literal["openai", "anthropic", "auto"] = Field(
        default="auto", alias="LLM_PROVIDER"
    )
    llm_model: Optional[str] = Field(default=None, alias="LLM_MODEL")
    llm_temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, alias="LLM_TEMPERATURE")
    llm_max_tokens: Optional[int] = Field(default=None, ge=1, alias="LLM_MAX_TOKENS")

    # Memory Services
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    database_url: str = Field(
        default="postgresql://localhost:5432/slovo", alias="DATABASE_URL"
    )

    # Voice Services
    stt_provider: str = Field(default="whisper", alias="STT_PROVIDER")
    tts_provider: str = Field(default="openai", alias="TTS_PROVIDER")

    # Agent Configuration
    agent_max_retries: int = Field(default=2, ge=0, le=5, alias="AGENT_MAX_RETRIES")
    agent_timeout: float = Field(default=60.0, ge=1.0, alias="AGENT_TIMEOUT")

    # Logging
    log_level: str = Field(default="info", alias="LOG_LEVEL")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
