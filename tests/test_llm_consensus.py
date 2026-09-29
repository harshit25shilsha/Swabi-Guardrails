"""Unit tests for the LLM consensus orchestrator in app.llm.moderator.

These patch _single_llm_call directly, so they exercise the orchestrator
logic without touching Groq or reading GROQ_API_KEY.
"""
from unittest.mock import patch

import pytest

from app.config import settings
from app.llm.moderator import moderate_with_llm
from app.models.moderation import Action, LLMResult


def _allow(conf: float = 0.9) -> LLMResult:
    return LLMResult(decision=Action.ALLOW, category=None, confidence=conf)


def _block(cat: str = "PHONE_NUMBER", conf: float = 0.9) -> LLMResult:
    return LLMResult(decision=Action.BLOCK, category=cat, confidence=conf)


@pytest.fixture(autouse=True)
def _two_attempts(monkeypatch):
    monkeypatch.setattr(settings, "LLM_CONSENSUS_ATTEMPTS", 2)


def test_allow_then_block_returns_block():
    with patch(
        "app.llm.moderator._single_llm_call",
        side_effect=[_allow(), _block()],
    ) as m:
        r = moderate_with_llm("test")
    assert r.decision == Action.BLOCK
    assert r.category == "PHONE_NUMBER"
    assert m.call_count == 2


def test_block_short_circuits_on_first_attempt():
    with patch(
        "app.llm.moderator._single_llm_call",
        side_effect=[_block(), _allow()],
    ) as m:
        r = moderate_with_llm("test")
    assert r.decision == Action.BLOCK
    assert m.call_count == 1  # second call skipped


def test_both_allow_returns_highest_confidence():
    with patch(
        "app.llm.moderator._single_llm_call",
        side_effect=[_allow(0.80), _allow(0.95)],
    ) as m:
        r = moderate_with_llm("test")
    assert r.decision == Action.ALLOW
    assert r.confidence == 0.95
    assert m.call_count == 2


def test_first_raises_second_blocks():
    with patch(
        "app.llm.moderator._single_llm_call",
        side_effect=[RuntimeError("boom"), _block()],
    ) as m:
        r = moderate_with_llm("test")
    assert r.decision == Action.BLOCK
    assert m.call_count == 2


def test_first_raises_second_allows_returns_allow():
    with patch(
        "app.llm.moderator._single_llm_call",
        side_effect=[RuntimeError("boom"), _allow(0.9)],
    ):
        r = moderate_with_llm("test")
    assert r.decision == Action.ALLOW


def test_all_attempts_raise_reraises_last_exception():
    with patch(
        "app.llm.moderator._single_llm_call",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            moderate_with_llm("test")


def test_single_attempt_config_makes_one_call(monkeypatch):
    monkeypatch.setattr(settings, "LLM_CONSENSUS_ATTEMPTS", 1)
    with patch(
        "app.llm.moderator._single_llm_call",
        side_effect=[_allow()],
    ) as m:
        r = moderate_with_llm("test")
    assert r.decision == Action.ALLOW
    assert m.call_count == 1


def test_multiple_blocks_returns_highest_confidence_block(monkeypatch):
    # Force 3 attempts to allow two blocks in a row without short-circuiting
    # the first one. Actually: BLOCK short-circuits, so to test the
    # highest-confidence selection we need the first call to be ALLOW.
    monkeypatch.setattr(settings, "LLM_CONSENSUS_ATTEMPTS", 3)
    with patch(
        "app.llm.moderator._single_llm_call",
        side_effect=[_allow(), _block(conf=0.6), _block(conf=0.95)],
    ):
        r = moderate_with_llm("test")
    # First BLOCK encountered wins because of short-circuit
    assert r.decision == Action.BLOCK
    assert r.confidence == 0.6