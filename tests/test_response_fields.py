from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test-token"}


def test_response_has_source_request_id_prompt_version():
    r = client.post(
        "/api/v1/validate-message",
        headers=AUTH,
        json={"message": "Call me at 9876543210"},
    )
    body = r.json()
    assert body["source"] == "deterministic"
    assert body["request_id"].startswith("gr_")
    assert body["prompt_version"].startswith("marketplace_")


def test_response_header_has_request_id():
    r = client.post(
        "/api/v1/validate-message",
        headers=AUTH,
        json={"message": "Call me at 9876543210"},
    )
    assert r.headers["x-request-id"].startswith("gr_")