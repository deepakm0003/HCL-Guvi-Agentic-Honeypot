"""Intelligence extraction layer with LLM and format validation."""

import json
import re
from typing import Any, Optional

from app.config import get_settings
from app.core.clients import get_openai_client
from app.models import ExtractedIntelligence
from app.utils.logging import get_logger
from app.utils.validators import (
    extract_and_validate_indian_phone,
    extract_and_validate_upi,
    extract_and_validate_url,
    extract_bank_account_pattern,
    sanitize_text,
)

logger = get_logger(__name__)

UPI_REGEX = re.compile(r"\b[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\b")
URL_REGEX = re.compile(r"https?://[^\s<>\"']+")
PHONE_REGEX = re.compile(r"(?:\+91|91)?[6-9]\d{9}\b")
BANK_ACCOUNT_REGEX = re.compile(r"(?:XXXX|[*]{4})[-]?(?:XXXX|[*]{4})[-]?\d{4,}|\d{4,}[-]?\d{4,}[-]?\d{4,}")


def _validate_upi(upi: str) -> bool:
    """Validate UPI ID format."""
    if not upi or len(upi) > 50:
        return False
    return bool(UPI_REGEX.match(upi))


def _validate_url(url: str) -> bool:
    """Validate URL format."""
    if not url or len(url) > 500:
        return False
    return url.startswith(("http://", "https://"))


def _validate_indian_phone(phone: str) -> bool:
    """Validate Indian phone format."""
    if not phone or len(phone) > 15:
        return False
    return bool(PHONE_REGEX.search(phone.replace(" ", "").replace("-", "")))


def _extract_from_text(text: str) -> ExtractedIntelligence:
    """Extract intelligence using regex/validation from raw text."""
    sanitized = sanitize_text(text)
    bank_accounts: list[str] = []
    upi_ids: list[str] = []
    phishing_links: list[str] = []
    phone_numbers: list[str] = []
    suspicious_keywords: list[str] = []

    # Bank accounts
    for match in BANK_ACCOUNT_REGEX.finditer(sanitized):
        val = match.group(0)
        if val not in bank_accounts:
            bank_accounts.append(val)
    acc = extract_bank_account_pattern(sanitized)
    if acc and acc not in bank_accounts:
        bank_accounts.append(acc)

    # UPI IDs
    for match in UPI_REGEX.finditer(sanitized):
        val = match.group(0)
        if _validate_upi(val) and val not in upi_ids:
            upi_ids.append(val)
    upi = extract_and_validate_upi(sanitized)
    if upi and upi not in upi_ids:
        upi_ids.append(upi)

    # URLs
    for match in URL_REGEX.finditer(sanitized):
        val = match.group(0)
        if _validate_url(val) and val not in phishing_links:
            phishing_links.append(val)
    url = extract_and_validate_url(sanitized)
    if url and url not in phishing_links:
        phishing_links.append(url)

    # Phone numbers
    for match in PHONE_REGEX.finditer(sanitized.replace(" ", "").replace("-", "")):
        raw = match.group(0)
        phone = extract_and_validate_indian_phone(raw)
        if phone and phone not in phone_numbers:
            phone_numbers.append(phone)
    phone = extract_and_validate_indian_phone(sanitized)
    if phone and phone not in phone_numbers:
        phone_numbers.append(phone)

    # Suspicious keywords
    scam_terms = [
        "urgent", "verify", "immediately", "blocked", "suspended",
        "upi", "otp", "kyc", "click link", "share", "transfer",
        "prize", "winner", "claim", "account blocked",
    ]
    lower = sanitized.lower()
    for term in scam_terms:
        if term in lower and term not in suspicious_keywords:
            suspicious_keywords.append(term)

    return ExtractedIntelligence(
        bank_accounts=bank_accounts,
        upi_ids=upi_ids,
        phishing_links=phishing_links,
        phone_numbers=phone_numbers,
        suspicious_keywords=suspicious_keywords,
    )


def _llm_extract(conversation_text: str) -> Optional[dict[str, Any]]:
    """Use LLM for structured intelligence extraction."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    try:
        client = get_openai_client()
        if not client:
            return None
        prompt = f"""Extract scam-related intelligence from this conversation. Return ONLY valid JSON with these exact keys (arrays of strings):
- bankAccounts: bank account numbers, masked formats like XXXX-XXXX-1234
- upiIds: UPI IDs (handle@bank format)
- phishingLinks: URLs that may be phishing/malicious
- phoneNumbers: Indian phone numbers (+91XXXXXXXXXX)
- suspiciousKeywords: scam-related phrases used

Conversation:
{conversation_text[:3000]}

Return ONLY the JSON object, no other text."""

        response = client.chat.completions.create(
            model=settings.openai_extraction_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        # Strip markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r"^```\w*\n?", "", content)
            content = re.sub(r"\n?```\s*$", "", content)
        parsed = json.loads(content)
        return parsed
    except Exception as e:
        logger.warning("LLM extraction failed", extra={"extra_data": {"error": str(e)}})
        return None


def merge_intelligence(
    existing: ExtractedIntelligence, new: ExtractedIntelligence
) -> ExtractedIntelligence:
    """Merge new extraction into existing, deduplicating."""
    bank = list(dict.fromkeys(existing.bank_accounts + new.bank_accounts))
    upi = list(dict.fromkeys(existing.upi_ids + new.upi_ids))
    links = list(dict.fromkeys(existing.phishing_links + new.phishing_links))
    phones = list(dict.fromkeys(existing.phone_numbers + new.phone_numbers))
    keywords = list(dict.fromkeys(existing.suspicious_keywords + new.suspicious_keywords))
    return ExtractedIntelligence(
        bankAccounts=bank,
        upiIds=upi,
        phishingLinks=links,
        phoneNumbers=phones,
        suspiciousKeywords=keywords,
    )


def extract_intelligence(
    conversation_history: list[dict],
    latest_message: str,
    existing: ExtractedIntelligence,
) -> ExtractedIntelligence:
    """Extract intelligence from conversation using LLM + validation."""
    full_text = latest_message
    for m in conversation_history:
        full_text += " " + m.get("text", "")

    # Regex-based extraction (always runs)
    regex_result = _extract_from_text(full_text)

    # LLM extraction (if available)
    llm_result = _llm_extract(full_text)
    if llm_result:
        llm_intel = ExtractedIntelligence(
            bank_accounts=[str(x) for x in llm_result.get("bankAccounts", []) if x],
            upi_ids=[str(x) for x in llm_result.get("upiIds", []) if x],
            phishing_links=[str(x) for x in llm_result.get("phishingLinks", []) if x],
            phone_numbers=[str(x) for x in llm_result.get("phoneNumbers", []) if x],
            suspicious_keywords=[str(x) for x in llm_result.get("suspiciousKeywords", []) if x],
        )
        merged = merge_intelligence(regex_result, llm_intel)
    else:
        merged = regex_result

    # Validate and filter
    validated_bank = [b for b in merged.bank_accounts if len(b) <= 30]
    validated_upi = [u for u in merged.upi_ids if _validate_upi(u)]
    validated_links = [l for l in merged.phishing_links if _validate_url(l)]
    validated_phones = [p for p in merged.phone_numbers if _validate_indian_phone(p)]
    validated_keywords = [k for k in merged.suspicious_keywords if len(k) <= 50]

    new_intel = ExtractedIntelligence(
        bank_accounts=validated_bank,
        upi_ids=validated_upi,
        phishing_links=validated_links,
        phone_numbers=validated_phones,
        suspicious_keywords=validated_keywords,
    )

    return merge_intelligence(existing, new_intel)
