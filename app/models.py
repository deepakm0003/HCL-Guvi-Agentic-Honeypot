"""Pydantic models for request/response and internal data structures."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# --- Request Models ---


class MessageItem(BaseModel):
    """Single message in conversation."""

    sender: Literal["scammer", "user"]
    text: str
    timestamp: str


class MetadataItem(BaseModel):
    """Optional metadata for the request."""

    channel: Optional[str] = None
    language: Optional[str] = None
    locale: Optional[str] = None


class HoneypotRequest(BaseModel):
    """Incoming honeypot API request."""

    session_id: str = Field(..., alias="sessionId")
    message: MessageItem
    conversation_history: list[MessageItem] = Field(
        default_factory=list, alias="conversationHistory"
    )
    metadata: Optional[MetadataItem] = None

    class Config:
        populate_by_name = True


# --- Response Models ---


class HoneypotResponse(BaseModel):
    """API response for honeypot endpoint."""

    status: Literal["success", "error"]
    reply: str


# --- Internal Service Models ---


class ScamDetectionResult(BaseModel):
    """Result from scam detection layer."""

    is_scam: bool
    confidence: float
    reason: str


class AgentResponse(BaseModel):
    """Result from agent layer."""

    reply: str
    engagement_score: float


class ExtractedIntelligence(BaseModel):
    """Structured intelligence extracted from conversation."""

    bank_accounts: list[str] = Field(default_factory=list, alias="bankAccounts")
    upi_ids: list[str] = Field(default_factory=list, alias="upiIds")
    phishing_links: list[str] = Field(default_factory=list, alias="phishingLinks")
    phone_numbers: list[str] = Field(default_factory=list, alias="phoneNumbers")
    suspicious_keywords: list[str] = Field(
        default_factory=list, alias="suspiciousKeywords"
    )

    class Config:
        populate_by_name = True

    def to_callback_format(self) -> dict[str, list[str]]:
        """Convert to callback payload format."""
        return {
            "bankAccounts": self.bank_accounts,
            "upiIds": self.upi_ids,
            "phishingLinks": self.phishing_links,
            "phoneNumbers": self.phone_numbers,
            "suspiciousKeywords": self.suspicious_keywords,
        }

    def total_items(self) -> int:
        """Count total extracted items."""
        return (
            len(self.bank_accounts)
            + len(self.upi_ids)
            + len(self.phishing_links)
            + len(self.phone_numbers)
            + len(self.suspicious_keywords)
        )


class SessionMemory(BaseModel):
    """Per-session memory stored in Redis."""

    session_id: str
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    extracted_intelligence: ExtractedIntelligence = Field(
        default_factory=ExtractedIntelligence
    )
    message_count: int = 0
    scam_detected: bool = False
    agent_notes: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for Redis storage."""
        return {
            "session_id": self.session_id,
            "conversation_history": self.conversation_history,
            "extracted_intelligence": self.extracted_intelligence.model_dump(
                by_alias=True
            ),
            "message_count": self.message_count,
            "scam_detected": self.scam_detected,
            "agent_notes": self.agent_notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionMemory":
        """Deserialize from Redis storage."""
        intel_data = data.get("extracted_intelligence", {})
        return cls(
            session_id=data.get("session_id", ""),
            conversation_history=data.get("conversation_history", []),
            extracted_intelligence=ExtractedIntelligence(**intel_data),
            message_count=data.get("message_count", 0),
            scam_detected=data.get("scam_detected", False),
            agent_notes=data.get("agent_notes", ""),
            created_at=data.get("created_at", ""),
        )
