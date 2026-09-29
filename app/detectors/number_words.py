import re

# Digit words in English, transliterated Hindi, and Devanagari.
# Order matters for multi-word tokens (e.g. "twenty one") — we match tokens
# individually, so we keep this as a flat set.
_DIGIT_WORDS = {
    # English
    "zero", "one", "two", "three", "four", "five", "six", "seven",
    "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
    "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
    # Transliterated Hindi (common spellings)
    "shunya", "sifar",
    "ek", "do", "teen", "tin", "char", "chaar", "panch", "paanch",
    "chhe", "chhah", "che", "saat", "sat", "aath", "ath",
    "nau", "no", "das", "dus",
    "gyarah", "gyara", "gyarah", "barah", "barha",
    "terah", "tera", "terha", "chaudah", "chauda",
    "pandrah", "pandra", "solah", "sola",
    "satrah", "satra", "atharah", "athara",
    "unnis", "unnees", "bees", "bees",
    # Devanagari
    "शून्य", "सिफ़र", "सिफर",
    "एक", "दो", "तीन", "चार", "पांच", "पाँच",
    "छह", "छः", "सात", "आठ", "नौ", "दस",
    "ग्यारह", "बारह", "तेरह", "चौदह", "पंद्रह",
    "सोलह", "सत्रह", "अठारह", "उन्नीस", "बीस",
}

# Minimum number of consecutive digit-words to consider suspicious.
# 3+ covers phone fragments; 2 would over-block (e.g. "do teen din").
_MIN_RUN = 3

_TOKEN_RE = re.compile(r"[\w\u0900-\u097F]+", re.UNICODE)


def detect_number_word_sequence(text: str) -> bool:
    """
    Detect messages where digits are spelled out as words in sequence,
    e.g. "aath saat teen chaar" (8 7 3 4) — a common phone-number evasion.
    """
    if not text:
        return False

    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]

    run = 0
    for token in tokens:
        if token in _DIGIT_WORDS:
            run += 1
            if run >= _MIN_RUN:
                return True
        else:
            run = 0

    return False