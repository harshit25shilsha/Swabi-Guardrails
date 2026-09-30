"""Per-request observability: request_id, timing, JSON log, counters."""
import hashlib
import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability import counters

logger = logging.getLogger("guardrail.request")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = "gr_" + uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        request.state.moderation_result = None
        request.state.message_hash = None

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "unhandled_exception",
                extra={"request_id": request_id, "path": request.url.path,
                       "latency_ms": round(elapsed_ms, 2)},
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id

        result = getattr(request.state, "moderation_result", None)
        if result is not None:
            counters.increment("requests_total")
            counters.observe_latency(elapsed_ms)
            counters.increment(f"source:{result.source}")

            if result.action.value == "BLOCK":
                counters.increment("blocks_total")
                if result.category is not None:
                    counters.increment(
                        f"blocks_by_category:{result.category.value}"
                    )
            else:
                counters.increment("allows_total")

            logger.info(
                "moderation",
                extra={
                    "event": "moderation",
                    "request_id": request_id,
                    "action": result.action.value,
                    "category": result.category.value if result.category else None,
                    "confidence": result.confidence,
                    "source": result.source,
                    "latency_ms": round(elapsed_ms, 2),
                    "message_hash": request.state.message_hash,
                    "prompt_version": result.prompt_version,
                },
            )

        return response