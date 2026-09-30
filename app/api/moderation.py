import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from typing import Optional

from app.config import settings
from app.llm.moderator import PROMPT_VERSION
from app.models.moderation import ModerationRequest, ModerationResponse
from app.services.moderation import moderate


def verify_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.GUARDRAIL_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


router = APIRouter(prefix="/api/v1", tags=["moderation"])


@router.post(
    "/validate-message",
    response_model=ModerationResponse,
    dependencies=[Depends(verify_token)],
)
async def validate_message(
    payload: ModerationRequest, request: Request
) -> ModerationResponse:
    result = moderate(payload.message)
    result.request_id = getattr(request.state, "request_id", "")
    result.prompt_version = PROMPT_VERSION

    # Stash for the observability middleware to log & count.
    request.state.moderation_result = result
    request.state.message_hash = hashlib.sha256(
        payload.message.encode("utf-8")
    ).hexdigest()[:16]

    return result