"""Document type classification with a TF-IDF + logistic regression model (scikit-learn).

The model is trained on built-in descriptions of each document type plus the OCR text of
every genuine reference document the administrator has uploaded, so it gets better as
references are added. Character n-grams keep it robust to OCR spelling mistakes.
"""

import random
import threading

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


def classify(text, reference_texts=None):
    """Return (best type id, probability, top-3 [(type id, probability)])."""
    model = _get_model(reference_texts or {})
    probabilities = model.predict_proba([text.lower()])[0]
    ranked = sorted(zip(model.classes_, probabilities), key=lambda item: -item[1])
    best, probability = ranked[0]
    return best, float(probability), [(label, round(float(p), 3)) for label, p in ranked[:3]]
