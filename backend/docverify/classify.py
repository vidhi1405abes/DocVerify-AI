"""Document type classification with a TF-IDF + logistic regression model (scikit-learn).

The model is trained on built-in descriptions of each document type plus the OCR text of
every genuine reference document the administrator has uploaded, so it gets better as
references are added. Character n-grams keep it robust to OCR spelling mistakes.
"""

import random
import re
import threading
from difflib import SequenceMatcher

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from .doc_types import DOCUMENT_TYPES

OTHER = "other"
OTHER_SEEDS = [
    "invoice bill to ship to quantity unit price amount tax gst subtotal grand total payment due",
    "dear sir madam i am writing to inform you regards sincerely yours letter subject reference",
    "bank statement account number ifsc opening balance closing balance debit credit transaction",
    "receipt thank you for your purchase order number item price total paid cash card",
]

_lock = threading.Lock()
_model = None
_trained_on = None


def _noisy(text, rng, rate=0.06):
    """Simulate OCR mistakes so the model does not rely on perfect spelling."""
    letters = list(text)
    for index in range(len(letters)):
        if letters[index].isalpha() and rng.random() < rate:
            letters[index] = rng.choice("abcdefghijklmnopqrstuvwxyz")
    return "".join(letters)


def _training_set(reference_texts):
    rng = random.Random(7)
    texts, labels = [], []
    for type_id, spec in DOCUMENT_TYPES.items():
        samples = list(spec["seeds"]) + list(reference_texts.get(type_id, []))
        for sample in samples:
            for _ in range(6):
                words = sample.split()
                rng.shuffle(words)
                texts.append(_noisy(" ".join(words[: max(12, int(len(words) * 0.7))]), rng))
                labels.append(type_id)
            texts.append(sample)
            labels.append(type_id)
    for sample in OTHER_SEEDS:
        for _ in range(6):
            texts.append(_noisy(sample, rng))
            labels.append(OTHER)
    return texts, labels


def _get_model(reference_texts):
    global _model, _trained_on
    key = tuple(sorted((t, len(v), sum(map(len, v))) for t, v in reference_texts.items()))
    with _lock:
        if _model is None or _trained_on != key:
            texts, labels = _training_set(reference_texts)
            model = make_pipeline(
                TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, lowercase=True),
                LogisticRegression(max_iter=2000, C=8),
            )
            model.fit(texts, labels)
            _model, _trained_on = model, key
        return _model


# Phrases and subjects that settle 10th versus 12th, which share almost all their wording.
# Phrases are matched on letters only, so OCR spacing and punctuation do not matter.
CLASS_PHRASES = {
    "marksheet12": ["seniorschoolcertificateexamination", "seniorsecondary", "highersecondary",
                    "intermediateexamination"],
    "marksheet10": ["secondaryschoolexamination", "highschoolexamination", "matriculation"],
}
# Short markers are matched as whole words: "Class X" must not match "Class XI" or "Class XII".
CLASS_MARKERS = {
    "marksheet12": (r"\bclass\s*(?:xii|12(?:th)?)\b|\baissce\b", "Class XII"),
    "marksheet10": (r"\bclass\s*(?:x|10(?:th)?)\b|\baisse\b", "Class X"),
}
CLASS_SUBJECTS = {
    "marksheet12": ["PHYSICS", "CHEMISTRY", "BIOLOGY", "ACCOUNTANCY", "BUSINESS STUDIES", "ECONOMICS",
                    "ENGLISH CORE", "POLITICAL SCIENCE", "PHYSICAL EDUCATION"],
    "marksheet10": ["SOCIAL SCIENCE", "SCIENCE", "SCIENCE & TECH", "HINDI COURSE-A", "HINDI COURSE-B"],
}


def _fuzzy_contains(haystack, phrase, threshold=0.85):
    if phrase in haystack:
        return True
    size = len(phrase)
    for start in range(0, max(len(haystack) - size + 1, 1), 2):
        window = haystack[start:start + size]
        matcher = SequenceMatcher(None, window, phrase, autojunk=False)
        if matcher.real_quick_ratio() >= threshold and matcher.ratio() >= threshold:
            return True
    return False


def class_evidence(text, subjects=()):
    """Decide 10th vs 12th from printed wording and subjects. Returns (type, reason) or None."""
    letters = re.sub(r"[^a-z]", "", text.lower())
    # 12th is checked first: "Senior Secondary School Examination" contains the 10th phrase.
    for type_id in ("marksheet12", "marksheet10"):
        pattern, label = CLASS_MARKERS[type_id]
        if re.search(pattern, text, re.IGNORECASE):
            return type_id, f"the document says \"{label}\""
        for phrase in CLASS_PHRASES[type_id]:
            if _fuzzy_contains(letters, phrase):
                return type_id, f"the document says \"{phrase_label(phrase)}\""
    names = {row["subject"].upper() for row in subjects}
    for type_id in ("marksheet12", "marksheet10"):
        found = sorted(s for s in CLASS_SUBJECTS[type_id] if s in names)
        if found:
            return type_id, f"it lists {', '.join(s.title() for s in found[:3])}"
    return None


AADHAAR_PHRASES = ["governmentofindia", "uniqueidentificationauthority", "aadhaar", "aadhar"]


def aadhaar_evidence(text):
    """Aadhaar cards carry a 4-4-4 digit number, 'Government of India', a birth date and a gender.

    Returns a reason when at least two of these are present, even in badly read text."""
    letters = re.sub(r"[^a-z]", "", text.lower())
    markers = []
    if re.search(r"\b(?:\d{4}|[xX*]{4})\s\d{4}\s\d{4}\b|\b[xX*]{4}\s[xX*]{4}\s\d{4}\b", text):
        markers.append("a 12-digit Aadhaar-style number")
    if any(_fuzzy_contains(letters, phrase, 0.8) for phrase in AADHAAR_PHRASES):
        markers.append("Government of India / Aadhaar wording")
    if re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", text) and re.search(r"(female|male)", text, re.IGNORECASE):
        markers.append("a birth date and gender")
    return f"it shows {' and '.join(markers)}" if len(markers) >= 2 else None


def type_evidence(text, subjects=()):
    """Printed evidence of the document type: (type, reason) or None."""
    reason = aadhaar_evidence(text)
    if reason:
        return "aadhaar", reason
    return class_evidence(text, subjects)


def phrase_label(phrase):
    return {
        "seniorschoolcertificateexamination": "Senior School Certificate Examination",
        "seniorsecondary": "Senior Secondary", "highersecondary": "Higher Secondary",
        "intermediateexamination": "Intermediate Examination",
        "secondaryschoolexamination": "Secondary School Examination",
        "highschoolexamination": "High School Examination", "matriculation": "Matriculation",
    }[phrase]


def classify(text, reference_texts=None):
    """Return (best type id, probability, top-3 [(type id, probability)])."""
    model = _get_model(reference_texts or {})
    probabilities = model.predict_proba([text.lower()])[0]
    ranked = sorted(zip(model.classes_, probabilities), key=lambda item: -item[1])
    best, probability = ranked[0]
    return best, float(probability), [(label, round(float(p), 3)) for label, p in ranked[:3]]
