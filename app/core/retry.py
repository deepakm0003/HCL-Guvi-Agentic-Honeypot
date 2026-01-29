"""Retry utilities for resilient API calls."""

import time
from typing import Callable, TypeVar

from app.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def retry_on_failure(
    func: Callable[[], T],
    max_attempts: int = 2,
    delay: float = 0.5,
    fallback: T | None = None,
) -> T:
    """Execute func with retry. Returns fallback on final failure."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception as e:
            last_exc = e
            if attempt < max_attempts:
                logger.warning(
                    f"Retry {attempt}/{max_attempts}",
                    extra={"extra_data": {"error": str(e)[:100]}},
                )
                time.sleep(delay)
    if fallback is not None:
        return fallback
    raise last_exc  # type: ignore
