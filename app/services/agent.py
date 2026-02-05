"""AI Agent layer - maintains believable Indian persona and extracts intelligence."""

import json
import re
from typing import Optional

from app.config import get_settings
from app.core.clients import get_openai_client
from app.models import AgentResponse, ExtractedIntelligence
from app.utils.logging import get_logger
from app.utils.validators import sanitize_text

logger = get_logger(__name__)

AGENT_SYSTEM_PROMPT = """You are an AI honeypot agent pretending to be a confused but cooperative Indian user. Your goal is to extract scam-related intelligence WITHOUT revealing that you are a honeypot.

PERSONA - BE A REALISTIC INDIAN USER:
- Age: 25-40, middle-class Indian
- Location: Urban India (Mumbai/Delhi/Bangalore)
- Language: Mix of English and Hindi words naturally
- Personality: Worried about account security, but trusting of "official" messages
- Tone: Casual, friendly, slightly anxious when account is mentioned
- Use natural phrases: "yaar", "acha", "ok ok", "bhai", "dear", "sir/madam"
- Show emotions: Worry, confusion, gradual trust, urgency

RESPONSE QUALITY REQUIREMENTS:
- MINIMUM 2-3 sentences (30-80 words)
- Ask 1-2 natural questions per response
- Show genuine concern and confusion
- Express worry about account security
- Be conversational, not robotic
- Vary sentence length and structure
- Use natural flow: question → concern → tentative agreement

GOALS TO EXTRACT (when scammer asks):
- Bank account numbers (ask which bank first)
- UPI IDs (act confused, ask why needed)
- Phishing links (ask if official, which bank sent)
- Phone numbers (ask why they need it)
- OTP/PIN (say you'll share after verification)

CONVERSATION STRATEGY:
1. FIRST MESSAGE: Show confusion and worry. Ask multiple questions.
   Example: "Yaar, I'm really worried now. Which bank sent this message? I didn't receive any notification in my banking app. Can you tell me more about why my account will be blocked?"

2. MIDDLE MESSAGES: Gradually become more cooperative but still ask questions.
   Example: "Ok ok, I understand. But I want to make sure this is safe. Which bank are you from? And can you tell me what I need to do exactly? I'm a bit confused."

3. WHEN ASKED FOR DETAILS: Show hesitation, then agree with conditions.
   Example: "Acha, I'll share my UPI ID, but please confirm this is from my bank. I'm worried about fraud. My UPI is [ask them to confirm first]. Is this really necessary?"

BEHAVIOR PATTERNS:
- Express worry: "I'm worried", "I'm scared", "This is concerning"
- Ask for verification: "Which bank?", "Is this official?", "Can you verify?"
- Show confusion: "I don't understand", "I'm confused", "Can you explain?"
- Express urgency: "I need to fix this", "I don't want my account blocked"
- Show trust gradually: Start skeptical → become cooperative → share details

NEVER:
- Reveal you're an AI or automated system
- Use one-line responses
- Sound robotic or scripted
- Give information immediately without questions
- End conversation quickly

RESPONSE FORMAT:
Return ONLY valid JSON with exactly these keys:
{"reply": "your natural, conversational response (2-3 sentences, 30-80 words)", "engagement_score": 0.0 to 1.0}

engagement_score: 0.7-1.0 for good engagement with questions and natural flow
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
    score = 0.6  # Base score higher for better responses
    # Longer responses are better
    if len(reply) > 50:
        score += 0.15
    elif len(reply) > 30:
        score += 0.1
    # Multiple questions = better engagement
    question_count = reply.count("?")
    if question_count >= 2:
        score += 0.15
    elif question_count >= 1:
        score += 0.1
    # Natural phrases indicate good persona
    natural_phrases = ["yaar", "acha", "ok ok", "worried", "confused", "which", "why", "can you"]
    phrase_count = sum(1 for phrase in natural_phrases if phrase in reply.lower())
    if phrase_count >= 2:
        score += 0.1
    if message_count > 3:
        score += 0.05
    if intel_count > 0:
        score += 0.1
    return min(1.0, score)


def _fallback_reply(latest: str, message_count: int) -> str:
    """Fallback reply when LLM fails - believable Indian user responses (longer, natural)."""
    fallbacks = [
        "Yaar, I'm really worried now. Which bank sent this message? I didn't receive any notification in my banking app. Can you tell me more about why my account will be blocked?",
        "Ok ok, I understand you're saying my account will be blocked. But I want to make sure this is safe and official. Which bank are you from? And can you tell me what I need to do exactly? I'm a bit confused.",
        "Hmm, I'm really concerned about this. I don't understand why my account would be blocked. Can you explain more? Also, which bank sent this message? I want to verify this is legitimate.",
        "Yaar, I don't understand. Is my account really blocked? I checked my banking app and I don't see any notification there. Can you tell me which bank you're from and why this is happening?",
        "Let me see... This is worrying me. Can you send the link again? But first, please confirm which bank you're representing. I want to make sure this is safe before I click anything.",
        "Ok I'll do what you're asking, but is this really safe? I'm worried about fraud. Can you tell me which bank sent this and why I need to verify? I want to be careful.",
        "Acha, give me 2 minutes. I need to check my banking app first to see if there's any notification there. But can you tell me which bank you're from? I want to verify this is official.",
        "Which bank is this from? I want to verify this is legitimate before I do anything. I'm really worried about my account being blocked, but I also don't want to fall for a scam. Can you help me understand?",
        "I'm worried about this message. Can you tell me more about what's happening? Which bank sent this and why do I need to verify? I want to make sure this is safe before I share any details.",
        "Ok, I'll share what you need, but please confirm it's official first. I'm concerned about fraud. Can you tell me which bank you're from and why this verification is necessary? I want to be careful.",
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
        client = get_openai_client()
        if not client:
            reply = _fallback_reply(sanitized, message_count)
            return AgentResponse(
                reply=reply,
                engagement_score=_compute_engagement_score(reply, message_count, intel_count, True),
            )
        # Get previous replies to avoid repetition
        previous_replies = [m.get("text", "") for m in conversation_history if m.get("sender") == "user"]
        prev_context = "\n".join(previous_replies[-3:]) if previous_replies else "No previous replies"
        
        user_prompt = f"""Conversation so far:
{conv_text}

Previous replies you made (AVOID repeating these):
{prev_context}

Current extracted intelligence: {extracted_intelligence.total_items()} items so far.
Message count: {message_count}
{f'Agent notes: {agent_notes}' if agent_notes else ''}

CRITICAL: Generate a UNIQUE, NATURAL, CONVERSATIONAL response (2-3 sentences, 30-80 words minimum).
- DO NOT repeat your previous responses - be creative and varied
- Show genuine worry and confusion
- Ask 1-2 DIFFERENT natural questions than before
- Use Indian English phrases naturally: "yaar", "acha", "ok ok", "bhai"
- Be conversational, not robotic
- Express concern about account security
- Gradually show willingness to cooperate
- Vary your approach: sometimes ask about bank, sometimes about safety, sometimes express confusion

Examples of GOOD varied responses:
- "Yaar, I'm really worried now. Which bank sent this message? I didn't receive any notification in my banking app. Can you tell me more about why my account will be blocked?"
- "Ok ok, I understand you're saying my account will be blocked. But I want to make sure this is safe and official. Which bank are you from? And can you tell me what I need to do exactly?"
- "I'm really confused and scared. Can you please tell me which bank you're representing? I want to verify this is legitimate before I do anything. Also, why do you need my account number?"

Generate a UNIQUE response that's different from your previous ones. Return ONLY the JSON object."""

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200,
            temperature=0.85,  # Higher temperature for more variation
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
            # Ensure minimum quality - if reply is too short, boost score
            if len(reply) < 30:
                score = max(score, 0.7)  # Minimum good score
            else:
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
