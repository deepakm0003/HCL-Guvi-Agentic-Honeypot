"""Callback service - sends final result to GUVI evaluation endpoint."""

import time
from typing import Optional

import requests

from app.config import get_settings
from app.models import ExtractedIntelligence
from app.utils.logging import get_logger

logger = get_logger(__name__)


def send_final_callback(
    session_id: str,
    scam_detected: bool,
    total_messages: int,
    extracted_intelligence: ExtractedIntelligence,
    agent_notes: str,
) -> bool:
    """Send final result to GUVI callback endpoint. Retries up to 3 times."""
    settings = get_settings()
    payload = {
        "sessionId": session_id,
        "scamDetected": scam_detected,
        "totalMessagesExchanged": total_messages,
        "extractedIntelligence": extracted_intelligence.to_callback_format(),
        "agentNotes": agent_notes or "Engagement completed",
    }

    for attempt in range(1, settings.callback_retries + 1):
        try:
            response = requests.post(
                settings.callback_url,
                json=payload,
                timeout=settings.callback_timeout,
                headers={"Content-Type": "application/json"},
            )
            logger.info(
                "Callback response",
                extra={
                    "extra_data": {
                        "session_id": session_id,
                        "status_code": response.status_code,
                        "attempt": attempt,
                    }
                },
            )
            if response.status_code >= 200 and response.status_code < 300:
                return True
            if attempt < settings.callback_retries:
                time.sleep(1)
        except requests.RequestException as e:
            logger.warning(
                "Callback failed",
                extra={
                    "extra_data": {
                        "session_id": session_id,
                        "attempt": attempt,
                        "error": str(e),
                    }
                },
            )
            if attempt < settings.callback_retries:
                time.sleep(1)
    return False
