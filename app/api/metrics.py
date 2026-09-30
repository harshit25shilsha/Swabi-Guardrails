"""Operational endpoints. No auth — bind behind the firewall only."""
import time

from fastapi import APIRouter, Response

from app.config import settings
from app.llm.moderator import PROMPT_VERSION
from app.observability import counters
from app.llm.moderator import PROMPT_VERSION, llm_circuit

router = APIRouter(tags=["observability"])
_START_TIME = time.time()


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "service_version": settings.SERVICE_VERSION,
        "prompt_version": PROMPT_VERSION,
    }


@router.get("/metrics")
def metrics() -> Response:
    snap = counters.snapshot()
    lines = [
        "# HELP guardrail_requests_total Total moderation requests",
        "# TYPE guardrail_requests_total counter",
        f"guardrail_requests_total {snap['requests_total']}",
        "",
        "# HELP guardrail_allows_total Allowed messages",
        "# TYPE guardrail_allows_total counter",
        f"guardrail_allows_total {snap['allows_total']}",
        "",
        "# HELP guardrail_blocks_total Blocked messages",
        "# TYPE guardrail_blocks_total counter",
        f"guardrail_blocks_total {snap['blocks_total']}",
        "",
        "# HELP guardrail_blocks_by_category Blocks by category",
        "# TYPE guardrail_blocks_by_category counter",
    ]
    for cat, count in sorted(snap["blocks_by_category"].items()):
        lines.append(
            f'guardrail_blocks_by_category{{category="{cat}"}} {count}'
        )
    lines.extend([
        "",
        "# HELP guardrail_sources Decisions by source",
        "# TYPE guardrail_sources counter",
    ])
    for src, count in sorted(snap["sources"].items()):
        lines.append(f'guardrail_sources{{source="{src}"}} {count}')
    lines.extend([
        "",
        "# HELP guardrail_llm_calls_total Groq API calls made",
        "# TYPE guardrail_llm_calls_total counter",
        f"guardrail_llm_calls_total {snap['llm_calls_total']}",
        "",
        "# HELP guardrail_llm_failures_total Groq call failures",
        "# TYPE guardrail_llm_failures_total counter",
        f"guardrail_llm_failures_total {snap['llm_failures_total']}",
        "",
        "# HELP guardrail_fail_open_total Fail-open responses",
        "# TYPE guardrail_fail_open_total counter",
        f"guardrail_fail_open_total {snap['fail_open_total']}",
        "",
        "# HELP guardrail_latency_p95_ms Request latency p95 (ms)",
        "# TYPE guardrail_latency_p95_ms gauge",
        f"guardrail_latency_p95_ms {snap['latency_p95_ms']}",
        "",
    ])
    circuit = llm_circuit.metrics()
    lines.extend([
        "",
        "# HELP guardrail_circuit_state Circuit breaker state (1 if active)",
        "# TYPE guardrail_circuit_state gauge",
        f'guardrail_circuit_state{{state="closed"}} '
        f'{1 if circuit["state"] == "closed" else 0}',
        f'guardrail_circuit_state{{state="open"}} '
        f'{1 if circuit["state"] == "open" else 0}',
        f'guardrail_circuit_state{{state="half_open"}} '
        f'{1 if circuit["state"] == "half_open" else 0}',
        "",
        "# HELP guardrail_circuit_trips_total Times the circuit opened",
        "# TYPE guardrail_circuit_trips_total counter",
        f'guardrail_circuit_trips_total {circuit["trips_total"]}',
        "",
        "# HELP guardrail_circuit_rejections_total Requests short-circuited",
        "# TYPE guardrail_circuit_rejections_total counter",
        f'guardrail_circuit_rejections_total {circuit["rejections_total"]}',
        "",
    ])
    return Response(
        "\n".join(lines),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
    