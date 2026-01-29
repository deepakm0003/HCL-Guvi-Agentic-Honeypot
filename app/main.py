"""FastAPI application - Agentic Honeypot API."""

import time
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.config import get_settings
from app.models import HoneypotRequest, HoneypotResponse
from app.services.agent import generate_reply
from app.services.detector import detect_scam
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


def _error_response(reply: str) -> HoneypotResponse:
    """Return evaluation-compliant error response."""
    return HoneypotResponse(status="error", reply=reply)


@app.get("/")
async def root() -> dict[str, str]:
    """Root route - prevents 404 when visiting base URL."""
    return {
        "service": "Agentic Honeypot API",
        "status": "ok",
        "honeypot": "POST /honeypot",
        "health": "GET /health",
    }


@app.get("/ready")
async def ready() -> dict[str, str]:
    """Evaluation readiness check - fast, no auth required."""
    return {"ready": "true", "service": "honeypot"}


def _run_extraction_and_lifecycle(
    session_id: str,
    history: list[dict],
    latest_text: str,
    existing_intel,
    agent_notes: str,
    scam_detected: bool,
) -> None:
    """Background task: extract intelligence, update memory, check lifecycle."""
    from app.services.extractor import extract_intelligence

    try:
        memory = load_session(session_id)
        if memory is None:
            return
        memory.extracted_intelligence = extract_intelligence(
            conversation_history=history,
            latest_message=latest_text,
            existing=existing_intel,
        )
        intel_count = memory.extracted_intelligence.total_items()
        memory.agent_notes = _build_agent_notes(
            memory.agent_notes, "", latest_text, intel_count
        )
        if should_end_engagement(memory):
            check_and_end_if_needed(memory)
        save_session(memory)
    except Exception as e:
        logger.exception(
            "Background extraction failed",
            extra={"extra_data": {"session_id": session_id, "error": str(e)}},
        )


@app.post("/honeypot", response_model=HoneypotResponse)
async def honeypot_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
) -> HoneypotResponse:
    """Main honeypot endpoint - evaluation-ready, always returns {status, reply}."""
    start_time = time.perf_counter()
    settings = get_settings()

    # Auth - 401 for invalid key (evaluation validates this)
    try:
        _verify_api_key(x_api_key)
    except HTTPException:
        raise

    # Wrap entire logic - never crash, always return valid JSON
    try:
        # Request size limit (evaluation readiness)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_request_body_size:
                    return _error_response("Request too large")
            except ValueError:
                pass

        body = await request.json()
        honeypot_req = HoneypotRequest(**body)
    except (RequestValidationError, ValidationError) as e:
        logger.warning("Validation error", extra={"extra_data": {"errors": str(e)}})
        return _error_response("Invalid request format")
    except Exception as e:
        logger.warning("Invalid request body", extra={"extra_data": {"error": str(e)}})
        return _error_response("Invalid request format")

    session_id = honeypot_req.session_id
    if not validate_session_id(session_id):
        return _error_response("Invalid session ID")

    message = honeypot_req.message
    if not validate_message_text(message.text):
        return _error_response("Invalid message text")

    sanitized_text = sanitize_text(message.text)
    if not sanitized_text:
        return HoneypotResponse(
            status="success",
            reply="I didn't understand. Can you repeat?",
        )

    try:
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

        # If scam detected: activate agent
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

            # Add agent reply to history
            history_as_dicts.append({
                "sender": "user",
                "text": reply,
                "timestamp": message.timestamp,
            })
            memory.conversation_history = history_as_dicts
            memory.message_count = len(history_as_dicts)

            # Run extraction + lifecycle in background
            background_tasks.add_task(
                _run_extraction_and_lifecycle,
                session_id,
                history_as_dicts[:-1],
                sanitized_text,
                memory.extracted_intelligence,
                memory.agent_notes,
                memory.scam_detected,
            )

        save_session(memory)

        elapsed = time.perf_counter() - start_time
        if elapsed > settings.max_response_time_seconds:
            logger.warning(
                "Response exceeded target time",
                extra={"extra_data": {"session_id": session_id, "elapsed": elapsed}},
            )

        return HoneypotResponse(status="success", reply=reply)

    except Exception as e:
        logger.exception(
            "Honeypot endpoint error",
            extra={"extra_data": {"session_id": session_id, "error": str(e)}},
        )
        return _error_response("Something went wrong. Please try again.")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint - fast, no external dependencies."""
    return {"status": "ok", "service": "honeypot"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return evaluation-compliant format for validation errors on honeypot."""
    if request.url.path == "/honeypot":
        return JSONResponse(
            status_code=200,
            content={"status": "error", "reply": "Invalid request format"},
        )
    raise exc


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never crash - return evaluation-compliant JSON."""
    from fastapi import HTTPException

    if isinstance(exc, HTTPException):
        if exc.status_code == 401:
            raise exc
        if request.url.path == "/honeypot":
            return JSONResponse(
                status_code=200,
                content={"status": "error", "reply": str(exc.detail)[:200]},
            )
        raise exc
    logger.exception(
        "Unhandled exception",
        extra={"extra_data": {"path": request.url.path, "error": str(exc)}},
    )
    if request.url.path == "/honeypot":
        return JSONResponse(
            status_code=200,
            content={"status": "error", "reply": "Something went wrong. Please try again."},
        )
    return JSONResponse(
        status_code=500,
        content={"status": "error", "reply": "Something went wrong. Please try again."},
    )
