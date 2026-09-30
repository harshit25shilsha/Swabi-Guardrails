from fastapi import FastAPI, Request

from app.api.metrics import router as metrics_router
from app.api.moderation import router as moderation_router
from app.config import settings
from app.observability.logging_setup import setup_logging
from app.observability.middleware import ObservabilityMiddleware

setup_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)

app = FastAPI(
    title="Guardrail Service",
    version=settings.SERVICE_VERSION,
    description="Synchronous LLM-powered chat moderation layer for the marketplace.",
)

app.add_middleware(ObservabilityMiddleware)

app.include_router(metrics_router)          # /health, /metrics
app.include_router(moderation_router)       # /api/v1/validate-message