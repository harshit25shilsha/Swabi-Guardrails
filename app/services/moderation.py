import logging

from app.detectors.email import detect_email
from app.detectors.normalize import normalize
from app.detectors.payment import detect_payment
from app.detectors.phone import detect_phone
from app.detectors.url import detect_url
from app.llm.moderator import moderate_with_llm
from app.models.moderation import (
    Action,
    ModerationCategory,
    ModerationResponse,
)
from app.policies.policy import apply_policy

from app.detectors.number_words import detect_number_word_sequence
from app.detectors.encoded_digits import detect_encoded_digits
from app.detectors.arithmetic_digits import detect_arithmetic_digits
from app.observability import counters
from app.observability.circuit_breaker import CircuitOpenError

logger = logging.getLogger(__name__)

# Order matters. Email before URL so "@" forms are classified as EMAIL.
# (Detector fn, category, confidence)
_DETERMINISTIC_CHECKS = [
    (detect_phone,   ModerationCategory.PHONE_NUMBER,        0.99),
    (detect_number_word_sequence, ModerationCategory.PHONE_NUMBER, 0.8),
    (detect_encoded_digits, ModerationCategory.PHONE_NUMBER, 0.8),
    (detect_arithmetic_digits, ModerationCategory.PHONE_NUMBER, 0.85),
    (detect_email,   ModerationCategory.EMAIL,               0.99),
    (detect_payment, ModerationCategory.PAYMENT_INFORMATION, 0.97),
    (detect_url,     ModerationCategory.EXTERNAL_URL,        0.95),
]


def moderate(raw_message: str) -> ModerationResponse:
    text = normalize(raw_message)

    # 1) Deterministic layer — skip the LLM when an obvious violation is found.
    for detector, category, confidence in _DETERMINISTIC_CHECKS:
        try:
            if detector(text):
                return ModerationResponse(
                    allowed=False,
                    action=Action.BLOCK,
                    category=category,
                    confidence=confidence,
                    source="deterministic",
                )
        except Exception:
            # A broken detector must not take the whole request down.
            logger.exception("Detector %s raised", detector.__name__)

    # 2) LLM layer.
    try:
        llm_result = moderate_with_llm(text)
    except CircuitOpenError:
        # Expected during a Groq outage - no traceback needed.
        logger.warning("LLM circuit open; failing open")
        counters.increment("fail_open_total")
        return ModerationResponse(
            allowed=True,
            action=Action.ALLOW,
            category=None,
            confidence=0.0,
            source="fail_open",
        )
    except Exception:
        
        logger.exception("LLM moderation failed; failing open")
        counters.increment("fail_open_total")
        
        return ModerationResponse(
            allowed=True,
            action=Action.ALLOW,
            category=None,
            confidence=0.0,
            source="fail_open",
        )

    # 3) Policy layer — final decision.
    action, category, confidence = apply_policy(llm_result)
    return ModerationResponse(
        allowed=(action == Action.ALLOW),
        action=action,
        category=category,
        confidence=confidence,
        source="llm",
    )