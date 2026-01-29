"""Redis-based per-session memory layer."""

import json
from typing import Optional

from app.config import get_settings
from app.models import ExtractedIntelligence, SessionMemory
from app.utils.logging import get_logger

logger = get_logger(__name__)

# In-memory fallback when Redis is unavailable
_memory_fallback: dict[str, str] = {}


def _get_redis_client():
    """Get Redis client or None if unavailable."""
    try:
        from redis import Redis
        settings = get_settings()
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        logger.warning("Redis unavailable, using in-memory fallback", extra={"extra_data": {"error": str(e)}})
        return None


def _redis_key(session_id: str) -> str:
    """Generate Redis key for session."""
    return f"honeypot:session:{session_id}"


def load_session(session_id: str) -> Optional[SessionMemory]:
    """Load session memory from Redis."""
    settings = get_settings()
    client = _get_redis_client()

    if client:
        try:
            data = client.get(_redis_key(session_id))
            if data:
                parsed = json.loads(data)
                return SessionMemory.from_dict(parsed)
        except Exception as e:
            logger.exception("Failed to load session from Redis", extra={"extra_data": {"session_id": session_id, "error": str(e)}})
            return None
    else:
        # In-memory fallback
        fallback_data = _memory_fallback.get(_redis_key(session_id))
        if fallback_data:
            try:
                parsed = json.loads(fallback_data)
                return SessionMemory.from_dict(parsed)
            except Exception:
                pass
    return None


def save_session(memory: SessionMemory) -> bool:
    """Save session memory to Redis."""
    settings = get_settings()
    client = _get_redis_client()

    data_str = json.dumps(memory.to_dict())

    if client:
        try:
            key = _redis_key(memory.session_id)
            client.setex(key, settings.redis_session_ttl, data_str)
            return True
        except Exception as e:
            logger.exception("Failed to save session to Redis", extra={"extra_data": {"session_id": memory.session_id, "error": str(e)}})
            return False
    else:
        key = _redis_key(memory.session_id)
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
