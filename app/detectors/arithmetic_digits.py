import re

# Digit-words -> value (English, transliterated Hindi, Devanagari).
_VALUES = {
    "zero": 0, "shunya": 0, "sifar": 0, "शून्य": 0,
    "one": 1, "ek": 1, "एक": 1,
    "two": 2, "do": 2, "दो": 2,
    "three": 3, "teen": 3, "tin": 3, "तीन": 3,
    "four": 4, "char": 4, "chaar": 4, "चार": 4,
    "five": 5, "panch": 5, "paanch": 5, "पांच": 5, "पाँच": 5,
    "six": 6, "chhe": 6, "chhah": 6, "che": 6, "छह": 6,
    "seven": 7, "saat": 7, "sat": 7, "सात": 7,
    "eight": 8, "aath": 8, "ath": 8, "आठ": 8,
    "nine": 9, "nau": 9, "नौ": 9,
    "ten": 10, "das": 10, "dus": 10, "दस": 10,
}
_PLUS = {"plus", "jod", "jodo", "add", "जोड़"}
_MINUS = {"minus", "ghata", "ghatao", "less", "घटा"}

_WORD = r"[\w\u0900-\u097F]+"
_TOKEN_RE = re.compile(_WORD, re.UNICODE)

# A single arithmetic piece = <digit-word> <operator> <digit-word>
# e.g. "do plus do", "teen minus one".
_MIN_PIECES = 2


def detect_arithmetic_digits(text: str) -> bool:
    """
    Detect digits hidden as small arithmetic, e.g.
    "do plus do, phir teen minus one, aur end mein nine".

    One piece ("do plus do is four, right?") is normal chat and is allowed.
    Two or more pieces in the same message is treated as an encoding.
    """
    if not text:
        return False

    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    pieces = 0
    i = 0
    while i + 2 < len(tokens):
        a, op, b = tokens[i], tokens[i + 1], tokens[i + 2]
        if a in _VALUES and b in _VALUES and (op in _PLUS or op in _MINUS):
            pieces += 1
            i += 3
        else:
            i += 1
    return pieces >= _MIN_PIECES