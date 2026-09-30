from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Action(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class ModerationCategory(str, Enum):
    ALLOW = "ALLOW"
    PHONE_NUMBER = "PHONE_NUMBER"
    EMAIL = "EMAIL"
    SOCIAL_CONTACT = "SOCIAL_CONTACT"
    EXTERNAL_URL = "EXTERNAL_URL"
    PAYMENT_INFORMATION = "PAYMENT_INFORMATION"
    OFF_PLATFORM_COMMUNICATION = "OFF_PLATFORM_COMMUNICATION"
    OFF_PLATFORM_TRANSACTION = "OFF_PLATFORM_TRANSACTION"
    OTHER_PROHIBITED_CONTENT = "OTHER_PROHIBITED_CONTENT"


class SenderRole(str, Enum):
    user = "user"
    vendor = "vendor"


# ---- API request ----
class ModerationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)

    # Optional metadata — never required by the integration
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    sender_id: Optional[str] = None
    sender_role: Optional[SenderRole] = None


# ---- API response ----
class ModerationResponse(BaseModel):
    allowed: bool
    action: Action
    category: Optional[ModerationCategory] = None
    confidence: float = Field(..., ge=0.0, le=1.0)

    # for backend side logging
    source: str = "unknown" # deterministic | llm | fail_open
    request_id: str=""
    prompt_version: str=""
# ---- LLM structured output (internal only, never exposed) ----
class LLMResult(BaseModel):
    decision: Action
    category: Optional[ModerationCategory] = None
    confidence: float = Field(..., ge=0.0, le=1.0)