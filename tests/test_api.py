from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.moderation import LLMResult

client = TestClient(app)

AUTH = {"Authorization": "Bearer test-token"}


def test_missing_token():
    r = client.post("/api/v1/validate-message", json={"message": "hi"})
    assert r.status_code == 401


def test_invalid_token():
    r = client.post(
        "/api/v1/validate-message",
        headers={"Authorization": "Bearer wrong"},
        json={"message": "hi"},
    )
    assert r.status_code == 401


def test_missing_message_field():
    r = client.post("/api/v1/validate-message", headers=AUTH, json={})
    assert r.status_code == 422


def test_phone_blocked_via_api():
    r = client.post(
        "/api/v1/validate-message",
        headers=AUTH,
        json={"message": "Call me at 9876543210"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is False
    assert body["action"] == "BLOCK"
    assert body["category"] == "PHONE_NUMBER"


def test_allow_via_api_uses_llm():
    with patch("app.services.moderation.moderate_with_llm") as mock_llm:
        mock_llm.return_value = LLMResult(
            decision="ALLOW", category=None, confidence=0.98
        )
        r = client.post(
            "/api/v1/validate-message",
            headers=AUTH,
            json={"message": "Is the villa available?"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["allowed"] is True
        assert body["category"] is None