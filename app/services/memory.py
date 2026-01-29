"""Redis-based per-session memory layer with connection pooling."""

import json
import threading
from typing import Optional

from app.config import get_settings
from app.models import ExtractedIntelligence, SessionMemory
from app.utils.logging import get_logger

logger = get_logger(__name__)

# In-memory fallback when Redis is unavailable
_memory_fallback: dict[str, str] = {}
_fallback_lock = threading.Lock()

# Redis connection pool (singleton)
_redis_client: Optional[object] = None
_redis_lock = threading.Lock()


def _get_redis_client() -> Optional[object]:
    """Get Redis client with connection pooling. Returns None if unavailable."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.ping()  # type: ignore
            return _redis_client
        except Exception:
            _redis_client = None

    with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        try:
            from redis import Redis
            settings = get_settings()
            client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            client.ping()
            _redis_client = client
            return _redis_client
        except Exception as e:
            logger.warning(
                "Redis unavailable, using in-memory fallback",
                extra={"extra_data": {"error": str(e)}},
            )
            return None


def _redis_key(session_id: str) -> str:
    """Generate Redis key for session."""
    return f"honeypot:session:{session_id}"


def load_session(session_id: str) -> Optional[SessionMemory]:
    """Load session memory from Redis or in-memory fallback."""
    client = _get_redis_client()

    if client:
        try:
            data = client.get(_redis_key(session_id))  # type: ignore
            if data:
                parsed = json.loads(data)
                return SessionMemory.from_dict(parsed)
        except Exception as e:
            logger.warning(
                "Failed to load session from Redis",
                extra={"extra_data": {"session_id": session_id, "error": str(e)}},
            )
            return None
    else:
        with _fallback_lock:
            fallback_data = _memory_fallback.get(_redis_key(session_id))
        if fallback_data:
            try:
                parsed = json.loads(fallback_data)
                return SessionMemory.from_dict(parsed)
            except Exception:
                pass
    return None


def save_session(memory: SessionMemory) -> bool:
    """Save session memory to Redis or in-memory fallback."""
    settings = get_settings()
    client = _get_redis_client()
    data_str = json.dumps(memory.to_dict())
    key = _redis_key(memory.session_id)

    if client:
        try:
            client.setex(key, settings.redis_session_ttl, data_str)
            return True
        except Exception as e:
            logger.warning(
                "Failed to save session to Redis, using fallback",
                extra={"extra_data": {"session_id": memory.session_id, "error": str(e)}},
            )
            with _fallback_lock:
                _memory_fallback[key] = data_str
            return True
    else:
        with _fallback_lock:
            _memory_fallback[key] = data_str
        return True


def create_session(session_id: str) -> SessionMemory:
    """Create new session memory."""
    from datetime import datetime
    return SessionMemory(
        session_id=session_id,
        conversation_history=[],
        extracted_intelligence=ExtractedIntelligence(),
        message_count=0,
        scam_detected=False,
        agent_notes="",
        created_at=datetime.utcnow().isoformat() + "Z",
    )


def check_redis_available() -> bool:
    """Check if Redis is available (for health check)."""
    client = _get_redis_client()
    return client is not None
