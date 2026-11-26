"""Helpers for reading numbers, dates and identifiers out of noisy OCR text."""

import re
from datetime import date
from difflib import SequenceMatcher
from itertools import takewhile

MONTHS = {
    name: index
    for index, names in enumerate(
        [
            ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
            ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
            ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}

UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}
TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
    "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
    "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20,
    "thirtieth": 30,
}

# Characters OCR commonly confuses with digits inside numeric fields.
DIGIT_LOOKALIKES = str.maketrans({"O": "0", "o": "0", "D": "0", "Q": "0", "I": "1", "l": "1",
                                  "|": "1", "i": "1", "S": "5", "s": "5", "B": "8", "Z": "2",
                                  "z": "2", "G": "6", "g": "9"})


DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
DEVANAGARI = "ऀ-ॿ"


def ascii_digits(text):
    """Hindi documents often print numbers in Devanagari digits (२०२०); read them as 2020."""
    return text.translate(DEVANAGARI_DIGITS)


def has_devanagari(text):
    return bool(re.search(f"[{DEVANAGARI}]", text or ""))


def normalized_text(text):
    """Lower-case letters and digits only, keeping Hindi letters so Hindi values still compare."""
    return re.sub(f"[^a-z0-9{DEVANAGARI}]", "", ascii_digits(text).casefold())


def to_digits(token):
    """Read a token that should be numeric, fixing common OCR look-alikes."""
    cleaned = ascii_digits(token.strip()).translate(DIGIT_LOOKALIKES)
    return cleaned if re.fullmatch(r"[0-9]+", cleaned) else None


def words_to_number(text):
    """'SEVENTY NINE' -> 79, 'ONE HUNDRED' -> 100. Returns None if not a number phrase."""
    words = re.findall(r"[a-z]+", text.casefold())
    if not words:
        return None
    total, current, seen = 0, 0, False
    for word in words:
        if word in UNITS:
            current += UNITS[word]
        elif word in TENS:
            current += TENS[word]
        elif word == "hundred":
            current = (current or 1) * 100
        elif word == "thousand":
            total += (current or 1) * 1000
            current = 0
        elif word == "and":
            continue
        else:
            return None
        seen = True
    return total + current if seen else None


def year_from_words(text):
    """'NINETEEN HUNDRED NINETY' / 'NINETEEN NINETY' / 'TWO THOUSAND FIVE' -> int."""
    number_words = set(UNITS) | set(TENS) | {"hundred", "thousand", "and"}
    words = list(takewhile(lambda w: w in number_words, re.findall(r"[a-z]+", text.casefold())))
    if not words:
        return None
    text = " ".join(words)
    if words[0] in UNITS and UNITS[words[0]] >= 10 and "thousand" not in words:
        century = UNITS[words[0]]
        rest = [w for w in words[1:] if w not in ("hundred", "and")]
        tail = words_to_number(" ".join(rest)) if rest else 0
        if tail is None or tail >= 100:
            return None
        return century * 100 + tail
    return words_to_number(text)


def parse_date(text):
    """Find the first date in text: 12/05/2006, 12-05-06, 12 May 2006, 1ST DECEMBER NINETEEN..."""
    if not text:
        return None
    numeric = re.search(r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})\b", text)
    if numeric:
        day, month, year = (int(part) for part in numeric.groups())
        if year < 100:
            year += 2000 if year < 50 else 1900
        return _safe_date(year, month, day)

    month_names = "|".join(sorted(MONTHS, key=len, reverse=True))
    named = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s*[ ,.-]?\s*({month_names})[a-z]*\.?\s*[ ,.-]?\s*(\d{{4}})\b",
        text,
        re.IGNORECASE,
    )
    if named:
        return _safe_date(int(named.group(3)), MONTHS[named.group(2).casefold()], int(named.group(1)))

    worded = re.search(
        rf"\b([a-z0-9]+?)(?:st|nd|rd|th)?\s+({month_names})[a-z]*\s+([a-z ]+)",
        text,
        re.IGNORECASE,
    )
    if worded:
        day_token = worded.group(1).casefold()
        day = int(day_token) if day_token.isdigit() else ORDINALS.get(day_token) or words_to_number(day_token)
        year = year_from_words(worded.group(3))
        if day and year:
            return _safe_date(year, MONTHS[worded.group(2).casefold()], day)
    return None


def _safe_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff_valid(number):
    """Aadhaar numbers end in a Verhoeff check digit."""
    checksum = 0
    for index, digit in enumerate(reversed(number)):
        checksum = _VERHOEFF_D[checksum][_VERHOEFF_P[index % 8][int(digit)]]
    return checksum == 0


def similarity(a, b):
    return SequenceMatcher(None, normalized_text(a), normalized_text(b)).ratio()
