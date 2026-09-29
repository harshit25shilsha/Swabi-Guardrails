import pytest
from app.detectors.number_words import detect_number_word_sequence


@pytest.mark.parametrize("text", [
    "aath saat teen chaar, or firr uske bad gyarah terah satrah",
    "eight seven three four five six",
    "ek do teen char paanch chhe",
    "आठ सात तीन चार",
    "one two three four",
])
def test_detects_number_word_run(text):
    assert detect_number_word_sequence(text) is True


@pytest.mark.parametrize("text", [
    "do din ka rent kitna hai?",           # 2 digit-words, legit
    "teen raat ke liye booking",           # 1 digit-word, legit
    "paanch sau rupaye discount milega?",  # 1 digit-word, legit
    "Is the villa available?",             # no digit-words
    "aath saat",                           # only 2, below threshold
])
def test_no_false_positive(text):
    assert detect_number_word_sequence(text) is False
    
