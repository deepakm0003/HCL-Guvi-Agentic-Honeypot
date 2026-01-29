"""Scam detection layer with hybrid keyword + LLM logic."""

import re
from typing import Optional

from openai import OpenAI

from app.config import get_settings
from app.models import ScamDetectionResult
from app.utils.logging import get_logger
from app.utils.validators import sanitize_text

logger = get_logger(__name__)

# Scam keyword patterns with weights
SCAM_KEYWORDS: list[tuple[str, float]] = [
    (r"\b(verify|verification)\s+(immediately|now|urgent)\b", 0.3),
    (r"\baccount\s+(blocked|suspended|locked)\b", 0.35),
    (r"\bupi\s*(id|pin)\b", 0.25),
    (r"\b(share|send|provide)\s+(your|ur)\s+(upi|bank)\b", 0.3),
    (r"\b(click|visit)\s+(link|url)\b", 0.25),
    (r"\b(urgent|immediately|asap)\b", 0.15),
    (r"\b(otp|pin)\s+(required|needed)\b", 0.25),
    (r"\b(won|winner|prize|reward)\s+(claim|collect)\b", 0.3),
    (r"\b(kyc|verification)\s+(pending|required)\b", 0.25),
    (r"\b(bank|sbi|hdfc|icici)\s+(account|block)\b", 0.3),
    (r"\bphishing|malicious\b", 0.5),
    (r"\b(transfer|send)\s+money\b", 0.2),
    (r"\b\d{10,12}\s*(call|whatsapp)\b", 0.2),
]


def _keyword_score(text: str) -> float:
    """Compute keyword-based scam score (0-0.5)."""
    sanitized = sanitize_text(text)
    if not sanitized:
        return 0.0
    score = 0.0
    for pattern, weight in SCAM_KEYWORDS:
        if re.search(pattern, sanitized, re.IGNORECASE):
            score += weight
    return min(0.5, score)


def _llm_classify(text: str, conversation_context: str) -> tuple[bool, float, str]:
    """Use LLM to classify scam intent. Returns (is_scam, confidence, reason)."""
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set, using keyword-only detection")
        kw_score = _keyword_score(text)
        return kw_score >= 0.5, kw_score, "Keyword-based detection (no LLM)"

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        prompt = f"""You are a scam/fraud intent classifier. Analyze the following message for scam or fraudulent intent (bank fraud, UPI fraud, phishing, fake offers, impersonation).

Message to analyze:
"{text}"

{f'Previous context: {conversation_context[:500]}' if conversation_context else ''}

Respond in exactly this format (no other text):
IS_SCAM: true/false
CONFIDENCE: 0.0 to 1.0
REASON: one short sentence explaining why"""

        response = client.chat.completions.create(
            model=settings.openai_detection_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        is_scam = False
        confidence = 0.0
        reason = "Unknown"

        for line in content.split("\n"):
            line = line.strip()
            if line.upper().startswith("IS_SCAM:"):
                val = line.split(":", 1)[1].strip().lower()
                is_scam = val in ("true", "yes", "1")
            elif line.upper().startswith("CONFIDENCE:"):
                try:
                    val = float(line.split(":", 1)[1].strip())
                    confidence = max(0.0, min(1.0, val))
                except ValueError:
                    pass
            elif line.upper().startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()

        return is_scam, confidence, reason
    except Exception as e:
        logger.exception("LLM detection failed, falling back to keywords", extra={"extra_data": {"error": str(e)}})
        kw_score = _keyword_score(text)
        return kw_score >= 0.5, kw_score, f"Fallback: keyword score (LLM error: {str(e)[:50]})"


def detect_scam(text: str, conversation_history: list[dict]) -> ScamDetectionResult:
    """Hybrid scam detection: keyword scoring + LLM classification."""
    sanitized = sanitize_text(text)
    if not sanitized:
        return ScamDetectionResult(is_scam=False, confidence=0.0, reason="Empty message")

    kw_score = _keyword_score(sanitized)
    # Skip LLM if keyword score is very high - faster response
    settings = get_settings()
    if kw_score >= 0.6 and kw_score >= settings.scam_confidence_threshold:
        return ScamDetectionResult(
            is_scam=True,
            confidence=kw_score,
            reason="High keyword match - scam indicators detected",
        )
    context = " ".join(m.get("text", "") for m in conversation_history[-5:])
    is_scam_llm, llm_conf, reason = _llm_classify(sanitized, context)

    # Combine: if keywords suggest scam, boost; otherwise trust LLM
    if kw_score >= 0.3:
        combined_confidence = max(llm_conf, kw_score + 0.2)
    else:
        combined_confidence = llm_conf

    combined_confidence = min(1.0, combined_confidence)
    is_scam = is_scam_llm or (kw_score >= 0.5 and combined_confidence >= 0.5)

    settings = get_settings()
    if combined_confidence >= settings.scam_confidence_threshold:
        is_scam = True

    return ScamDetectionResult(
        is_scam=is_scam,
        confidence=combined_confidence,
        reason=reason,
    )
