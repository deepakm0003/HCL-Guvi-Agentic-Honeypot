"""Pydantic models for request/response and internal data structures."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# --- Request Models ---


class MessageItem(BaseModel):
    """Single message in conversation."""

    sender: Literal["scammer", "user"]
    text: str = Field(default="", max_length=10000)
    timestamp: str = Field(default="", max_length=50)

    @field_validator("sender", mode="before")
    @classmethod
    def normalize_sender(cls, v: Any) -> str:
        """Accept case-insensitive sender."""
        if isinstance(v, str):
            return v.lower().strip()
        return v

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, v: Any) -> str:
        """Handle None or missing text."""
        if v is None:
            return ""
        return str(v) if v else ""

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, v: Any) -> str:
        """Handle None or empty timestamp."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        return str(v)


class MetadataItem(BaseModel):
    """Optional metadata for the request."""

    channel: Optional[str] = None
    language: Optional[str] = None
    locale: Optional[str] = None


class HoneypotRequest(BaseModel):
    """Incoming honeypot API request - tolerant of GUVI tester format."""

    session_id: str = Field(
        default="eval-session",
        alias="sessionId",
        min_length=1,
        max_length=128,
    )
    message: MessageItem
    conversation_history: list[MessageItem] = Field(
        default_factory=list, alias="conversationHistory", max_length=50
    )
    metadata: Optional[MetadataItem] = None

    @field_validator("conversation_history", mode="before")
    @classmethod
    def normalize_conversation_history(cls, v: Any) -> list:
        """Handle null or missing conversationHistory."""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []

    @field_validator("session_id", mode="before")
    @classmethod
    def normalize_session_id(cls, v: Any) -> str:
        """Handle sessionId - allow alphanumeric, hyphen, underscore, dot."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "eval-session"
        s = str(v).strip()
        return s if s else "eval-session"

    @field_validator("message", mode="before")
    @classmethod
    def normalize_message(cls, v: Any) -> dict:
        """Handle message as string (GUVI tester may send simplified format)."""
        if isinstance(v, str):
            return {
                "sender": "scammer",
                "text": v,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        return v

    class Config:
        populate_by_name = True
        extra = "ignore"  # Ignore unknown fields from tester


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
