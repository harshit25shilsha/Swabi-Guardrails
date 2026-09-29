import logging

from fastapi import FastAPI

from app.api.moderation import router as moderation_router
from app.config import settings

logging.basicConfig(level=settings.LOG_LEVEL.upper())

app = FastAPI(
    title="Guardrail Service",
    version="0.1.0",
    description="Synchronous LLM-powered chat moderation layer for the marketplace.",
)

app.include_router(moderation_router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}