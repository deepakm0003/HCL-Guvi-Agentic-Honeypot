"""Application configuration."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API
    api_key: str = "your-secret-api-key"
    api_key_header: str = "x-api-key"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_detection_model: str = "gpt-4o-mini"
    openai_extraction_model: str = "gpt-4o-mini"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_session_ttl: int = 3600  # 1 hour in seconds

    # Scam detection
    scam_confidence_threshold: float = 0.7

    # Lifecycle
    max_messages_before_end: int = 12
    min_intelligence_items_to_end: int = 2

    # Callback
    callback_url: str = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"
    callback_timeout: int = 5
    callback_retries: int = 3

    # Response
    max_response_time_seconds: float = 3.0

    # Limits (evaluation readiness)
    max_request_body_size: int = 100_000  # 100KB


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
