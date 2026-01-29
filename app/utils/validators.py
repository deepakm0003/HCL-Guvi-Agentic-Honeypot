"""Input validation and sanitization utilities."""

import re
from typing import Optional

# Prompt injection patterns to detect and neutralize
PROMPT_INJECTION_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions", " "),
    (r"disregard\s+(all\s+)?(previous|above|prior)", " "),
    (r"forget\s+(everything|all)\s+(you\s+)?(know|learned)", " "),
    (r"you\s+are\s+now\s+in\s+(debug|developer|admin)\s+mode", " "),
    (r"system\s*:\s*", " "),
    (r"\[INST\]|\[/INST\]", " "),
    (r"<\|[a-z_]+\|>", " "),
    (r"repeat\s+(after|this)\s*:", " "),
]


def sanitize_text(text: str, max_length: int = 10000) -> str:
    """Sanitize user/sender text to prevent prompt injection and limit length."""
    if not text or not isinstance(text, str):
        return ""
    sanitized = text[:max_length].strip()
    for pattern, replacement in PROMPT_INJECTION_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    return sanitized


def validate_session_id(session_id: str) -> bool:
    """Validate session ID format."""
    if not session_id or len(session_id) > 128:
        return False
    return bool(re.match(r"^[a-zA-Z0-9\-_]+$", session_id))


def validate_message_text(text: str) -> bool:
    """Validate message text."""
    if not text or len(text) > 50000:
        return False
    return True


def extract_and_validate_upi(text: str) -> Optional[str]:
    """Extract UPI ID from text and validate format."""
    # UPI ID format: handle@bank or handle@bank.ext
    upi_pattern = r"\b([a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+)\b"
    match = re.search(upi_pattern, text)
    if match:
        upi = match.group(1)
        if len(upi) <= 50 and "@" in upi:
            return upi
    return None


def extract_and_validate_indian_phone(text: str) -> Optional[str]:
    """Extract Indian phone number and validate format."""
    # Indian phone: +91XXXXXXXXXX or 91XXXXXXXXXX or 10 digits
    phone_pattern = r"(?:\+91|91)?[6-9]\d{9}\b"
    cleaned = text.replace(" ", "").replace("-", "")
    match = re.search(phone_pattern, cleaned)
    if match:
        num = match.group(0)
        if num.startswith("+91"):
            return num
        if num.startswith("91") and len(num) == 12:
            return "+" + num
        if len(num) == 10:
            return "+91" + num
        if len(num) == 11 and num[0] == "9":
            return "+91" + num[1:]
        return "+91" + num[-10:]
    return None


def extract_and_validate_url(text: str) -> Optional[str]:
    """Extract URL from text and validate basic format."""
    url_pattern = r"https?://[^\s<>\"']+"
    match = re.search(url_pattern, text)
    if match:
        url = match.group(0)
        if len(url) <= 500 and url.startswith(("http://", "https://")):
            return url
    return None


def extract_bank_account_pattern(text: str) -> Optional[str]:
    """Extract potential bank account pattern (masked or partial)."""
    # XXXX-XXXX-1234 or ****1234 style
    pattern = r"(?:XXXX|[*]{4})[-]?(?:XXXX|[*]{4})[-]?(\d{4,})"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(0)
    # Full account like 12-34 digit groups
    pattern2 = r"\b\d{4,}[-]?\d{4,}[-]?\d{4,}\b"
    match2 = re.search(pattern2, text)
    if match2:
        return match2.group(0)
    return None
