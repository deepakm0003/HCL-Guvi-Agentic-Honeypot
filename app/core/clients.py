"""Singleton clients with connection reuse and retry."""

from typing import Optional

from openai import OpenAI

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

_openai_client: Optional[OpenAI] = None


def get_openai_client() -> Optional[OpenAI]:
    """Get singleton OpenAI client with timeout. Returns None if no API key."""
    global _openai_client
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    if _openai_client is None:
        _openai_client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=20.0,
            max_retries=2,
        )
    return _openai_client


def reset_openai_client() -> None:
    """Reset client (for testing)."""
    global _openai_client
    _openai_client = None
