"""Lifecycle manager - decides when to end engagement and trigger callback."""

from app.config import get_settings
from app.models import ExtractedIntelligence, SessionMemory
from app.services.callback import send_final_callback
from app.utils.logging import get_logger

logger = get_logger(__name__)


def should_end_engagement(memory: SessionMemory) -> bool:
    """Decide if engagement should end based on lifecycle rules."""
    settings = get_settings()
    intel_count = memory.extracted_intelligence.total_items()

    # End if at least 12 messages exchanged
    if memory.message_count >= settings.max_messages_before_end:
        return True

    # End if at least 2 intelligence items extracted
    if intel_count >= settings.min_intelligence_items_to_end:
        return True

    return False


def end_engagement(memory: SessionMemory) -> bool:
    """End engagement: send callback and mark session complete."""
    if not memory.scam_detected:
        logger.info("Skipping callback - scam not detected", extra={"extra_data": {"session_id": memory.session_id}})
        return False

    success = send_final_callback(
        session_id=memory.session_id,
        scam_detected=memory.scam_detected,
        total_messages=memory.message_count,
        extracted_intelligence=memory.extracted_intelligence,
        agent_notes=memory.agent_notes,
    )
    if success:
        logger.info("Engagement ended, callback sent", extra={"extra_data": {"session_id": memory.session_id}})
    return success


def check_and_end_if_needed(memory: SessionMemory) -> bool:
    """Check lifecycle and end engagement if conditions met. Returns True if ended."""
    if not should_end_engagement(memory):
        return False
    return end_engagement(memory)
