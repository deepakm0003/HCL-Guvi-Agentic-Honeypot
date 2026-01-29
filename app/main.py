"""FastAPI application - Agentic Honeypot API."""

import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models import HoneypotRequest, HoneypotResponse
from app.services.agent import generate_reply
from app.services.detector import detect_scam
from app.services.extractor import extract_intelligence
from app.services.lifecycle import check_and_end_if_needed, should_end_engagement
from app.services.memory import create_session, load_session, save_session
from app.utils.logging import get_logger, setup_logging
from app.utils.validators import sanitize_text, validate_message_text, validate_session_id

setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Agentic Honeypot API",
    description="AI-powered honeypot for scam detection and intelligence extraction",
    version="1.0.0",
)


def _verify_api_key(api_key: Optional[str]) -> None:
    """Verify API key from header."""
    settings = get_settings()
    if not api_key or api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _build_agent_notes(
    existing_notes: str,
    detector_reason: str,
    latest_text: str,
    intel_count: int,
) -> str:
    """Build agent notes summarizing scammer behavior."""
    parts: list[str] = []
    if existing_notes:
        parts.append(existing_notes)
    if detector_reason:
        parts.append(f"Detection: {detector_reason[:100]}")
    if "upi" in latest_text.lower() or "bank" in latest_text.lower():
        parts.append("Requested payment/account details")
    if "link" in latest_text.lower() or "http" in latest_text.lower():
        parts.append("Shared/solicited link")
    if "otp" in latest_text.lower() or "pin" in latest_text.lower():
        parts.append("Requested OTP/PIN")
    if intel_count > 0:
        parts.append(f"Extracted {intel_count} intelligence items")
    return "; ".join(parts[-5:]) if len(parts) > 5 else "; ".join(parts)


@app.post("/honeypot", response_model=HoneypotResponse)
async def honeypot_endpoint(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
) -> HoneypotResponse:
    """Main honeypot endpoint - accepts message, detects scam, engages agent."""
    start_time = time.perf_counter()
    settings = get_settings()

    try:
        _verify_api_key(x_api_key)
    except HTTPException:
        raise

    try:
        body = await request.json()
        honeypot_req = HoneypotRequest(**body)
    except Exception as e:
        logger.warning("Invalid request body", extra={"extra_data": {"error": str(e)}})
        raise HTTPException(status_code=400, detail="Invalid request format")

    session_id = honeypot_req.session_id
    if not validate_session_id(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")

    message = honeypot_req.message
    if not validate_message_text(message.text):
        raise HTTPException(status_code=400, detail="Invalid message text")

    sanitized_text = sanitize_text(message.text)
    if not sanitized_text:
        return HoneypotResponse(
            status="success",
            reply="I didn't understand. Can you repeat?",
        )

    # Load or create session
    memory = load_session(session_id)
    if memory is None:
        memory = create_session(session_id)

    # Build conversation history
    history_as_dicts: list[dict] = list(memory.conversation_history)
    for m in honeypot_req.conversation_history:
        history_as_dicts.append({
            "sender": m.sender,
            "text": m.text,
            "timestamp": m.timestamp,
        })
    history_as_dicts.append({
        "sender": message.sender,
        "text": sanitized_text,
        "timestamp": message.timestamp,
    })

    # Run scam detection if not already detected
    if not memory.scam_detected:
        detection = detect_scam(sanitized_text, history_as_dicts[:-1])
        if detection.confidence >= settings.scam_confidence_threshold:
            memory.scam_detected = True
            memory.agent_notes = _build_agent_notes(
                memory.agent_notes,
                detection.reason,
                sanitized_text,
                0,
            )

    # Update message count
    memory.message_count = len(history_as_dicts)
    memory.conversation_history = history_as_dicts

    # If scam detected: activate agent, extract intelligence
    reply = "I'm not sure what you mean. Can you explain?"
    if memory.scam_detected:
        agent_response = generate_reply(
            latest_message=sanitized_text,
            conversation_history=history_as_dicts[:-1],
            extracted_intelligence=memory.extracted_intelligence,
            message_count=memory.message_count,
            agent_notes=memory.agent_notes,
        )
        reply = agent_response.reply

        # Extract intelligence
        memory.extracted_intelligence = extract_intelligence(
            conversation_history=history_as_dicts[:-1],
            latest_message=sanitized_text,
            existing=memory.extracted_intelligence,
        )

        # Update agent notes with extraction
        intel_count = memory.extracted_intelligence.total_items()
        memory.agent_notes = _build_agent_notes(
            memory.agent_notes,
            "",
            sanitized_text,
            intel_count,
        )

        # Add agent reply to history
        history_as_dicts.append({
            "sender": "user",
            "text": reply,
            "timestamp": message.timestamp,
        })
        memory.conversation_history = history_as_dicts
        memory.message_count = len(history_as_dicts)

        # Check lifecycle - end if conditions met
        if should_end_engagement(memory):
            check_and_end_if_needed(memory)

    save_session(memory)

    elapsed = time.perf_counter() - start_time
    if elapsed > settings.max_response_time_seconds:
        logger.warning(
            "Response exceeded target time",
            extra={"extra_data": {"session_id": session_id, "elapsed": elapsed}},
        )

    return HoneypotResponse(status="success", reply=reply)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "honeypot"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler - never crash API. Re-raises HTTPException."""
    from fastapi import HTTPException

    if isinstance(exc, HTTPException):
        raise exc
    logger.exception(
        "Unhandled exception",
        extra={"extra_data": {"path": request.url.path, "error": str(exc)}},
    )
    return JSONResponse(
        status_code=500,
        content={"status": "error", "reply": "Something went wrong. Please try again."},
    )
