from fastapi.testclient import TestClient

from app.main import app
from app.observability import counters

client = TestClient(app)
AUTH = {"Authorization": "Bearer test-token"}


def setup_function():
    counters.reset()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["uptime_seconds"] >= 0
    assert body["prompt_version"].startswith("marketplace_")


def test_metrics_endpoint_returns_prometheus_text():
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "guardrail_requests_total" in r.text
    assert "guardrail_latency_p95_ms" in r.text


def test_deterministic_block_updates_counters():
    client.post(
        "/api/v1/validate-message",
        headers=AUTH,
        json={"message": "Call me at 9876543210"},
    )
    text = client.get("/metrics").text
    assert "guardrail_requests_total 1" in text
    assert "guardrail_blocks_total 1" in text
    assert 'guardrail_blocks_by_category{category="PHONE_NUMBER"} 1' in text
    assert 'guardrail_sources{source="deterministic"} 1' in text


def test_latency_p95_recorded():
    for _ in range(5):
        client.post(
            "/api/v1/validate-message",
            headers=AUTH,
            json={"message": "Call me at 9876543210"},
        )
    text = client.get("/metrics").text
    assert "guardrail_latency_p95_ms" in text
    # Value must be a positive number
    for line in text.splitlines():
        if line.startswith("guardrail_latency_p95_ms "):
            value = float(line.split()[1])
            assert value > 0