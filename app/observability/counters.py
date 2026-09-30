# Thread-safe in-memory counters and latency tracker.

import threading
from collections import deque
from typing import Any

_lock = threading.Lock()
_counters: dict[str, int] = {}
_latencies: deque[float] = deque(maxlen=1000)   # last 1000 requests for p95


def increment(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + amount


def observe_latency(ms: float) -> None:
    with _lock:
        _latencies.append(ms)


def snapshot() -> dict[str, Any]:
    """Return a consistent snapshot of all counters + p95 latency."""
    with _lock:
        counters = dict(_counters)
        latencies = sorted(_latencies)

    p95 = 0.0
    if latencies:
        idx = min(int(len(latencies) * 0.95), len(latencies) - 1)
        p95 = latencies[idx]

    blocks_by_category = {
        k.split(":", 1)[1]: v
        for k, v in counters.items()
        if k.startswith("blocks_by_category:")
    }
    sources = {
        k.split(":", 1)[1]: v
        for k, v in counters.items()
        if k.startswith("source:")
    }

    return {
        "requests_total": counters.get("requests_total", 0),
        "blocks_total": counters.get("blocks_total", 0),
        "allows_total": counters.get("allows_total", 0),
        "llm_calls_total": counters.get("llm_calls_total", 0),
        "llm_failures_total": counters.get("llm_failures_total", 0),
        "fail_open_total": counters.get("fail_open_total", 0),
        "blocks_by_category": blocks_by_category,
        "sources": sources,
        "latency_p95_ms": round(p95, 2),
    }


def reset() -> None:
    """Test helper — clears all state."""
    with _lock:
        _counters.clear()
        _latencies.clear()