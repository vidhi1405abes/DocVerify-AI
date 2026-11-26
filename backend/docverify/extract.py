"""Turn OCR lines into structured fields (names, IDs, dates, marks) with pattern rules."""

import re
from difflib import SequenceMatcher, get_close_matches

from .textutils import parse_date, to_digits, words_to_number

NUMBER_WORDS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
    "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    "hundred",
]
GRADE = re.compile(r"^(?:[A-E][1-2I l]?|AI|AL|BI|CI|DI|EI)$", re.IGNORECASE)
MARK = re.compile(r"^(?:[0-9OoIlDBSZ]{2,3}|X{2,3}|AB)$", re.IGNORECASE)
NAME_NOISE = re.compile(r"[^A-Za-z .']")
CERTIFY_PHRASE = "thisistocertifythat"

# Label patterns tolerate common OCR slips (0/o, l/I, missing letters).
LABELS = {
    "rollNumber": r"\br[o0]ll\s*(?:n[o0o]|m[o0]|f[o0]|number|num)?\.?",
    "serialNumber": r"(?:s\.?\s*n[o0]\.?|serial\s*n[o0]\.?)",
    "applicationNumber": r"applica\w*\s*(?:n[o0]\.?|number)",
    "admissionNumber": r"admi\w*\s*(?:n[o0]\.?|number)",
    "certificateNumber": r"cert\w*\s*(?:n[o0]\.?|number)",
    "motherName": r"m[o0u]\w{2,4}\W{0,3}s?\s*n\w{2,3}e?",
    "fatherName": r"f[a-z]{2,4}er\W{0,3}s?.{0,22}?\bn[a-z]{2}[a-z]\b",
    "dateOfBirth": r"(?:d\w{2,3}\s*[o0]f\s*b\w{3,4}|\bd\.?\s*o\.?\s*b\.?|birth\s*date)",
    "school": r"\bsch\w{2,3}l\b(?!\W*(?:exam|cert|leav))(?:\s*name)?",
    "admissionDate": r"date\s*of\s*admi\w*",
    "leavingDate": r"date\s*of\s*leav\w*",
    "issueDate": r"(?:date\s*of\s*issue|issue\s*date|\bdated\b|\bdtd\b)",
    "class": r"\bclass\b",
    "gender": r"(?:gender|sex)",
    "district": r"district",
    "state": r"\bstate\b",
    "candidateName": r"(?:candidate\W?s?\s*name|name\s*of\s*(?:the\s*)?(?:candidate|pupil|student|applicant))",
}


def _clean(value):
    return re.sub(r"\s+", " ", value).strip(" :;,.-|")


def find_labelled(lines, key):
    """Text that follows a label on the same line (or the next line if empty)."""
    pattern = re.compile(LABELS[key] + r"\W*(.*)", re.IGNORECASE)
    for index, line in enumerate(lines):
        match = pattern.search(line.text)
        if match:
            value = _clean(match.group(1))
            if not value and index + 1 < len(lines):
                value = _clean(lines[index + 1].text)
            if value:
                return value, line
    return None, None


def _name(value):
    cleaned = _clean(NAME_NOISE.sub(" ", value or ""))
    words = [w for w in cleaned.split() if len(w) > 1 or w.isalpha()]
    return " ".join(words[:5]).upper() if len(cleaned) >= 3 else None


def _identifier(value, min_digits=5):
    if not value:
        return None
    run = re.search(r"\d[\dOoIlSB]{%d,}" % (min_digits - 1), value)
    digits = to_digits(run.group(0)) if run else None
    return digits if digits and len(digits) >= min_digits else None


def _confidence(line, text):
    if line is None:
        return None
    hits = [w.conf for w in line.words if text and w.text in text]
    return round(min(hits), 3) if hits else round(min(w.conf for w in line.words), 3)


class _Token:
    """A word with stray OCR punctuation removed from its edges."""

    def __init__(self, word):
        self.text = word.text.strip("'\"`{}()[]|,;:._-")
        self.conf = word.conf


def _parse_subject_line(line):
    words = [token for token in (_Token(w) for w in line.words) if token.text]
    if len(words) < 4:
        return None
    code = to_digits(words[0].text)
    if not code or not 2 <= len(code) <= 4:
        return None

    index, subject = 1, []
    while index < len(words) and not MARK.match(words[index].text):
        subject.append(words[index].text)
        index += 1
    marks = []
    while index < len(words) and MARK.match(words[index].text):
        marks.append(words[index])
        index += 1
    if not subject or not marks:
        return None

    rest = words[index:]
    grade = None
    if rest and GRADE.match(rest[-1].text):
        grade = rest[-1].text.upper().replace("I", "1").replace("L", "1")
        rest = rest[:-1]
    in_words = " ".join(w.text for w in rest)
    fixed_words = " ".join(
        (get_close_matches(word.casefold(), NUMBER_WORDS, n=1, cutoff=0.7) or [word])[0]
        for word in re.findall(r"[A-Za-z]+", in_words)
    )

    def value(word):
        if word.text.upper().startswith("X") or word.text.upper() == "AB":
            return None
        return int(to_digits(word.text)) if to_digits(word.text) else None

    numbers = [value(w) for w in marks]
    row = {
        "code": code,
        "subject": _clean(" ".join(subject)).upper(),
        "theory": None, "practical": None, "total": None,
        "totalInWords": in_words.upper() or None,
        "totalFromWords": words_to_number(fixed_words) if fixed_words else None,
        "grade": grade,
        "confidence": round(min(w.conf for w in marks), 3),
        "tokens": {},
    }
    if len(marks) >= 3:
        row["theory"], row["practical"], row["total"] = numbers[-3], numbers[-2], numbers[-1]
        row["tokens"] = {"theory": marks[-3].conf, "practical": marks[-2].conf, "total": marks[-1].conf}
    elif len(marks) == 2:
        row["theory"], row["total"] = numbers
        row["tokens"] = {"theory": marks[0].conf, "total": marks[1].conf}
    else:
        row["total"] = numbers[0]
        row["tokens"] = {"total": marks[0].conf}
    return row


def subject_rows(lines):
    rows = []
    for line in lines:
        row = _parse_subject_line(line)
        if row and row["total"] is not None and row["subject"] and len(row["subject"]) >= 3:
            rows.append(row)
    return rows


def _name_after_certify(line):
    """'This is to certify that NAME', tolerating OCR spellings like 'cetly thal'."""
    words = line.text.split()
    start = None
    for index in range(len(words) - 2):
        if (get_close_matches(words[index].casefold(), ["certify", "certified"], n=1, cutoff=0.6)
                and get_close_matches(words[index + 1].casefold(), ["that"], n=1, cutoff=0.5)):
            start = index + 2
            break
    if start is None:
        # Badly read openings such as "Tht /e t0 cstuily Lhal": compare the whole phrase.
        best = 0.0
        for count in range(3, min(len(words) - 1, 8)):
            letters = re.sub(r"[^a-z]", "", " ".join(words[:count]).casefold())
            score = SequenceMatcher(None, letters, CERTIFY_PHRASE).ratio()
            if score > best:
                best, start = score, count
        if best < 0.6:
            return None
    rest = " ".join(words[start:])
    rest = re.sub(r"^(?:shri|smt|kumari|mr|ms|miss)\.?\s+", "", rest, flags=re.I)
    return _name(re.split(r"\b(?:s/o|d/o|son|daughter|w/o)\b", rest, flags=re.I)[0])


def _name_above_roll_number(lines):
    """On board marksheets the candidate's name is printed on the line above the roll number."""
    roll = re.compile(LABELS["rollNumber"], re.IGNORECASE)
    for index, line in enumerate(lines[1:], start=1):
        if roll.search(line.text):
            for above in reversed(lines[max(0, index - 2):index]):
                # The name is the run of capitalised words at the end of the line.
                tail = []
                for word in reversed(above.text.split()):
                    if not re.fullmatch(r"[A-Z][A-Za-z.']+", word):
                        break
                    tail.insert(0, word)
                # Drop a misread "that" / "certify" left in front of the name.
                while tail and get_close_matches(tail[0].casefold(), ["that", "certify"], n=1, cutoff=0.5):
                    tail.pop(0)
                if 2 <= len(tail) <= 4:
                    return _name(" ".join(tail)), above
            return None, None
    return None, None


def _first(pattern, text, group=1, flags=re.IGNORECASE):
    match = re.search(pattern, text, flags)
    return match.group(group) if match else None


def extract_fields(document_type, ocr):
    """Return {field: value} plus per-field OCR confidence for the given document type."""
    lines = ocr.lines
    text = ocr.text
    fields, confidence = {}, {}

    def put(key, value, line=None):
        if value not in (None, "", []):
            fields[key] = value
            if line is not None:
                confidence[key] = _confidence(line, str(value))

    # Candidate name: "This is to certify that NAME", "Name of the candidate: NAME", "Name: NAME"
    for line in lines:
        name = _name_after_certify(line)
        if name:
            put("name", name, line)
            break
    if "name" not in fields:
        value, line = find_labelled(lines, "candidateName")
        put("name", _name(value), line)
    if "name" not in fields:
        value, line = _name_above_roll_number(lines)
        put("name", value, line)
    if "name" not in fields:
        for line in lines:
            match = re.match(r"^\s*name\s*[:\-]?\s*(.+)", line.text, re.I)
            if match:
                put("name", _name(match.group(1)), line)
                break

    for key in ("rollNumber", "applicationNumber", "admissionNumber", "certificateNumber", "serialNumber"):
        value, line = find_labelled(lines, key)
        put(key, _identifier(value, 4 if key == "serialNumber" else 5), line)

    for key in ("motherName", "fatherName"):
        value, line = find_labelled(lines, key)
        put(key, _name(value), line)

    value, line = find_labelled(lines, "dateOfBirth")
    if value:
        birth = parse_date(value)
        put("dateOfBirth", birth.isoformat() if birth else None, line)
        numeric = re.search(r"\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{2,4}", value)
        words_part = value[numeric.end():] if numeric else value
        worded = parse_date(words_part) if re.search(r"[a-z]{3}", words_part, re.I) else None
        if worded and re.search(r"\d", value) and worded != birth:
            put("dateOfBirthInWords", worded.isoformat(), line)
        elif worded and birth is None:
            put("dateOfBirth", worded.isoformat(), line)
        elif worded:
            put("dateOfBirthInWords", worded.isoformat(), line)

    for key in ("admissionDate", "leavingDate", "issueDate"):
        value, line = find_labelled(lines, key)
        parsed = parse_date(value) if value else None
        put(key, parsed.isoformat() if parsed else None, line)

    value, line = find_labelled(lines, "school")
    put("school", _clean(value).upper() if value and len(value) > 4 else None, line)

    for key in ("district", "state", "class"):
        value, line = find_labelled(lines, key)
        put(key, _clean(value).upper()[:60] if value else None, line)

    board = _first(r"(central board of secondary education|board of [a-z ]+education|national testing agency|"
                   r"unique identification authority of india|government of [a-z ]+)", text)
    put("board", board.upper() if board else None)
    exam = re.search(r"((?:all india\s+)?(?:secondary|senior|se\w{2,4})\s+school[a-z ]*examination|"
                     r"joint entrance examination[a-z() ]*)[\s,;:]*(\d{4})?", text, re.I)
    if exam:
        put("examination", _clean(exam.group(1)).upper())
        put("examYear", int(exam.group(2)) if exam.group(2) else None)

    result = _first(r"\bresult\b\W*(pass(?:ed)?|fail(?:ed)?|comp\w*|essential repeat)", text) or _first(
        r"\b(pass|passed|fail|failed|compartment)\b", text)
    put("result", result.upper() if result else None)

    rows = subject_rows(lines)
    if rows:
        fields["subjects"] = rows

    gender = _first(r"\b(male|female|transgender)\b", text)
    put("gender", gender.upper() if gender else None)

    full_aadhaar = re.search(r"\b([2-9]\d{3})\s?(\d{4})\s?(\d{4})\b", text)
    masked = re.search(r"\b[Xx*]{4}\s?[Xx*]{4}\s?(\d{4})\b", text)
    if document_type == "aadhaar":
        if full_aadhaar:
            put("aadhaarNumber", "".join(full_aadhaar.groups()))
        elif masked:
            put("aadhaarNumber", f"XXXXXXXX{masked.group(1)}")
        if "dateOfBirth" not in fields:
            year = _first(r"(?:year of birth|yob)\W*(\d{4})", text)
            put("dateOfBirth", f"{year}" if year else None)

    put("totalPercentile", _first(r"total\s*(?:nta\s*score|percentile)\W*(\d{1,3}\.\d+)", text)
        or _first(r"\bpercentile\b\W*(\d{1,3}\.\d+)", text))
    put("rank", _first(r"(?:all india rank|crl|air)\W*(\d{1,7})", text))
    put("cgpa", _first(r"\bc\.?g\.?p\.?a\.?\W*(\d{1,2}\.\d{1,2})", text))
    put("percentage", _first(r"(\d{2,3}\.\d{1,2})\s*%", text))
    put("grandTotal", _first(r"(?:grand\s*total|total\s*marks(?:\s*obtained)?)\W*(\d{2,4})", text))

    return fields, confidence
