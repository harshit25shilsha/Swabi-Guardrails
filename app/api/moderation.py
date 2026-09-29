from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import settings
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
async def validate_message(payload: ModerationRequest) -> ModerationResponse:
    return moderate(payload.message)