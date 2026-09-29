import pytest
from app.detectors.arithmetic_digits import detect_arithmetic_digits


@pytest.mark.parametrize("msg", [
    "do plus do, phir teen minus one, aur end mein nine",
    "teen plus char, then saat minus do",
    "दो plus दो, फिर तीन minus एक",
])
def test_detects_encoded_arithmetic(msg):
    assert detect_arithmetic_digits(msg)


@pytest.mark.parametrize("msg", [
    "do plus do is four, right?",
    "We need two rooms and one extra bed",
    "Is the car available tomorrow?",
    "",
])
def test_ignores_normal_chat(msg):
    assert not detect_arithmetic_digits(msg)