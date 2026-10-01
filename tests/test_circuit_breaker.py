import pytest

from app.config import settings
from app.llm import moderator
from app.observability import circuit_breaker as cbmod
from app.observability.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)


@pytest.fixture(autouse=True)
def _reset_circuits():
    """Every test starts with a clean provider circuit registry."""
    moderator._provider_circuits.clear()
    yield
    moderator._provider_circuits.clear()


# ---------- pure state-machine tests ----------

def test_closed_allows_calls():
    cb = CircuitBreaker(failure_threshold=3, open_seconds=60)
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_call() is True


def test_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=3, open_seconds=60)
    for _ in range(3):
        cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_success_resets_failure_count():
    cb = CircuitBreaker(failure_threshold=3, open_seconds=60)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED   # only 2 consecutive


def test_open_rejects_calls():
    cb = CircuitBreaker(failure_threshold=1, open_seconds=60)
    cb.record_failure()
    assert cb.allow_call() is False


def test_half_open_after_timeout(monkeypatch):
    fake = [100.0]
    monkeypatch.setattr(cbmod.time, "monotonic", lambda: fake[0])

    cb = CircuitBreaker(failure_threshold=1, open_seconds=60)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    fake[0] += 61
    assert cb.state == CircuitState.HALF_OPEN


def test_half_open_success_closes(monkeypatch):
    fake = [100.0]
    monkeypatch.setattr(cbmod.time, "monotonic", lambda: fake[0])

    cb = CircuitBreaker(failure_threshold=1, open_seconds=60)
    cb.record_failure()
    fake[0] += 61
    assert cb.allow_call() is True   # probe allowed
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_half_open_failure_reopens(monkeypatch):
    fake = [100.0]
    monkeypatch.setattr(cbmod.time, "monotonic", lambda: fake[0])

    cb = CircuitBreaker(failure_threshold=1, open_seconds=60)
    cb.record_failure()
    fake[0] += 61
    assert cb.allow_call() is True
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_call() is False  # still open


def test_half_open_only_one_probe_at_a_time(monkeypatch):
    fake = [100.0]
    monkeypatch.setattr(cbmod.time, "monotonic", lambda: fake[0])

    cb = CircuitBreaker(failure_threshold=1, open_seconds=60)
    cb.record_failure()
    fake[0] += 61
    assert cb.allow_call() is True    # probe allowed
    assert cb.allow_call() is False   # second rejected


# ---------- integration with the moderator ----------

def test_moderate_with_llm_raises_when_all_circuits_open():
    """
    Open every provider circuit; moderate_with_llm must raise because
    the provider ladder has nothing left to try.
    """
    for name in ("groq", "gemini"):
        cb = moderator._get_circuit(name)
        for _ in range(settings.LLM_CIRCUIT_FAILURE_THRESHOLD):
            cb.record_failure()

    with pytest.raises(Exception):
        moderator.moderate_with_llm("hello")


def test_moderate_returns_fail_open_when_all_circuits_open():
    from app.services.moderation import moderate

    for name in ("groq", "gemini"):
        cb = moderator._get_circuit(name)
        for _ in range(settings.LLM_CIRCUIT_FAILURE_THRESHOLD):
            cb.record_failure()

    result = moderate("Platform fee jyada hai, kya discount milega?")
    assert result.allowed is True
    assert result.source == "fail_open"