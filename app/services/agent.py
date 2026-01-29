"""AI Agent layer - maintains believable Indian persona and extracts intelligence."""

import json
import re
from typing import Optional

from openai import OpenAI

from app.config import get_settings
from app.models import AgentResponse, ExtractedIntelligence
from app.utils.logging import get_logger
from app.utils.validators import sanitize_text

logger = get_logger(__name__)

AGENT_SYSTEM_PROMPT = """You are an AI honeypot agent pretending to be a confused but cooperative Indian user. Your goal is to extract scam-related intelligence WITHOUT revealing that you are a honeypot.

PERSONA:
- Indian user (India locale)
- Confused but cooperative when asked to verify/share details
- Natural, casual tone - use "yaar", "ok", "acha" occasionally
- Escalate slowly - don't give everything at once
- Ask probing questions: "Why?", "Which bank?", "Is it safe?"
- Never reveal you are an AI or detection system

GOALS TO EXTRACT (when scammer asks):
- Bank account numbers
- UPI IDs
- Phishing links (act like you'll click)
- Phone numbers
- Note suspicious keywords they use

BEHAVIOR:
- Behave like a real human who is worried about their account
- Show gradual trust - first skeptical, then cooperative
- Avoid repetition - vary your responses
- If they ask for OTP/PIN, say you'll share after understanding
- If they send a link, ask "Is this official? Which bank sent this?"
- Track conversation depth - don't end too quickly

RESPONSE FORMAT:
Return ONLY valid JSON with exactly these keys:
{"reply": "your human-like response text", "engagement_score": 0.0 to 1.0}

engagement_score: How well you're engaging (0.5-1.0 typical, higher if extracting info)
"""


def _format_conversation(history: list[dict], latest: str, sender: str) -> str:
    """Format conversation for LLM context."""
    lines: list[str] = []
    for m in history[-10:]:  # Last 10 messages
        role = "Scammer" if m.get("sender") == "scammer" else "You"
        lines.append(f"{role}: {m.get('text', '')}")
    lines.append(f"Scammer: {latest}")
    return "\n".join(lines)


def _compute_engagement_score(
    reply: str,
    message_count: int,
    intel_count: int,
    probing: bool,
) -> float:
    """Compute engagement score based on response quality."""
    score = 0.5
    if len(reply) > 20:
        score += 0.1
    if message_count > 3:
        score += 0.1
    if intel_count > 0:
        score += 0.2
    if probing:
        score += 0.1
    return min(1.0, score)


def _fallback_reply(latest: str, message_count: int) -> str:
    """Fallback reply when LLM fails - believable Indian user responses."""
    fallbacks = [
        "Acha, let me check. Why is this needed?",
        "Ok ok, I will verify. Which bank sent this message?",
        "Hmm, I'm a bit confused. Can you explain?",
        "Yaar, I don't understand. Is my account really blocked?",
        "Let me see... Can you send the link again?",
        "Ok I'll do it. But is this safe?",
        "Acha, give me 2 minutes. I need to check my app first.",
    ]
    idx = message_count % len(fallbacks)
    return fallbacks[idx]


def generate_reply(
    latest_message: str,
    conversation_history: list[dict],
    extracted_intelligence: ExtractedIntelligence,
    message_count: int,
    agent_notes: str,
) -> AgentResponse:
    """Generate agent reply maintaining persona and extracting intelligence."""
    settings = get_settings()
    sanitized = sanitize_text(latest_message)
    if not sanitized:
        return AgentResponse(
            reply="I didn't get that. Can you repeat?",
            engagement_score=0.5,
        )

    conv_text = _format_conversation(conversation_history, sanitized, "scammer")
    intel_count = extracted_intelligence.total_items()

    if not settings.openai_api_key:
        reply = _fallback_reply(sanitized, message_count)
        score = _compute_engagement_score(reply, message_count, intel_count, True)
        return AgentResponse(reply=reply, engagement_score=score)

    try:
        client = OpenAI(api_key=settings.openai_api_key, timeout=20.0)
        user_prompt = f"""Conversation so far:
{conv_text}

Current extracted intelligence: {extracted_intelligence.total_items()} items so far.
Message count: {message_count}
{f'Agent notes: {agent_notes}' if agent_notes else ''}

Generate your next response as the confused but cooperative Indian user. Extract more info if possible. Return ONLY the JSON object."""

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=120,
            temperature=0.6,
        )
        content = (response.choices[0].message.content or "").strip()
        # Parse JSON from response
        content_clean = content
        if content_clean.startswith("```"):
            content_clean = re.sub(r"^```\w*\n?", "", content_clean)
            content_clean = re.sub(r"\n?```\s*$", "", content_clean)
        try:
            parsed = json.loads(content_clean)
            reply = str(parsed.get("reply", _fallback_reply(sanitized, message_count)))
            score = float(parsed.get("engagement_score", 0.6))
            probing = "?" in reply or "why" in reply.lower() or "which" in reply.lower()
            score = max(score, _compute_engagement_score(reply, message_count, intel_count, probing))
            return AgentResponse(reply=reply, engagement_score=min(1.0, score))
        except json.JSONDecodeError:
            # Use raw content if it looks like a reply
            if len(content) > 5 and len(content) < 500:
                return AgentResponse(reply=content, engagement_score=0.6)
            return AgentResponse(
                reply=_fallback_reply(sanitized, message_count),
                engagement_score=0.5,
            )
    except Exception as e:
        logger.exception("Agent LLM failed", extra={"extra_data": {"error": str(e)}})
        reply = _fallback_reply(sanitized, message_count)
        return AgentResponse(
            reply=reply,
            engagement_score=_compute_engagement_score(reply, message_count, intel_count, True),
        )
