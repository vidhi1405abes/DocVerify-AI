"""The verification engine: runs every layer and combines them into an explainable verdict."""

import threading
from difflib import SequenceMatcher
from pathlib import Path

from . import classify, consistency, extract, ocr, qr, tamper
from .config import SUPPORTED_EXTENSIONS
from .doc_types import DOCUMENT_TYPES, FIELD_LABELS
from .textutils import normalized_text, similarity

# How much each layer counts towards the risk score.
WEIGHTS = {
    "ocr": 5,
    "classification": 10,
    "structure": 15,
    "consistency": 25,
    "tampering": 20,
    "qr": 10,
    "records": 20,
    "reference": 15,
}
STATUS_RISK = {"pass": 0.0, "warn": 0.5, "fail": 1.0}
SUSPICIOUS_AT = 55
REVIEW_AT = 25
MIN_COVERAGE = 0.4
MATCH_THRESHOLD = 0.9
MIN_TEXT_LENGTH = 30

VERDICTS = {
    "verified": ("Verified", "Most verification checks passed and no signs of manipulation were found."),
    "review": ("Requires Review", "The system could not confidently verify this document. A person should "
                                  "inspect it."),
    "suspicious": ("Suspicious", "Several checks point to manipulation, inconsistent data or a record "
                                 "mismatch."),
}

_ocr_lock = threading.Lock()


def _layer(key, name, status, details, critical=False, extra=None):
    layer = {"key": key, "name": name, "status": status, "details": details, "weight": WEIGHTS[key],
             "critical": critical}
    if extra:
        layer.update(extra)
    return layer


def read_document(file_bytes, extension):
    """Load, preprocess and OCR a document. Returns (ocr result, colour pages, steps, pdf metadata)."""
    pages, metadata = ocr.load_pages(file_bytes, extension)
    grays, colours, steps = [], [], []
    for page in pages:
        gray, colour, page_steps = ocr.preprocess(page)
        grays.append(gray)
        colours.append(colour)
        steps.extend(step for step in page_steps if step not in steps)
    with _ocr_lock:
        result = ocr.read_text(grays)
    return result, colours, steps, metadata


def reference_text(path):
    """OCR text of a stored reference document, cached next to it."""
    cache = path.with_name(path.name + ".txt")
    if cache.exists():
        return cache.read_text(encoding="utf8")
    try:
        result, _, _, _ = read_document(path.read_bytes(), path.suffix.lower())
        text = result.text
    except ocr.UnreadableDocument:
        text = ""
    cache.write_text(text, encoding="utf8")
    return text


def list_references(reference_root, document_type):
    directory = Path(reference_root) / document_type
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)


def cached_reference_texts(reference_root):
    texts = {}
    for type_id in DOCUMENT_TYPES:
        for path in list_references(reference_root, type_id):
            cache = path.with_name(path.name + ".txt")
            if cache.exists():
                texts.setdefault(type_id, []).append(cache.read_text(encoding="utf8"))
    return texts


# ---------------------------------------------------------------- layers

def ocr_layer(result):
    if result.word_count < 5 or len(normalized_text(result.text)) < MIN_TEXT_LENGTH:
        return _layer("ocr", "Text extraction (OCR)", "fail",
                      ["Too little text could be read. Upload a clearer, straight-on scan or photo."])
    confidence = round(result.mean_confidence * 100)
    details = [f"Read {result.word_count} text regions with {confidence}% average OCR confidence."]
    if result.mean_confidence < 0.35:
        details.append("Low OCR confidence: some values may be misread.")
        return _layer("ocr", "Text extraction (OCR)", "warn", details)
    return _layer("ocr", "Text extraction (OCR)", "pass", details)


def classification_layer(selected, text, reference_texts):
    predicted, probability, ranked = classify.classify(text, reference_texts)
    selected_probability = dict(ranked).get(selected, 0.0)
    names = {k: v["name"] for k, v in DOCUMENT_TYPES.items()} | {"other": "an unrelated document"}
    extra = {"detectedType": predicted, "detectedTypeName": names[predicted],
             "probability": round(probability, 3),
             "ranking": [{"type": t, "name": names[t], "probability": p} for t, p in ranked]}
    if predicted == selected:
        return _layer("classification", "Document classification", "pass",
                      [f"Content matches a {names[selected]} ({round(probability * 100)}% confidence)."],
                      extra=extra)
    if selected_probability >= 0.2:
        return _layer("classification", "Document classification", "warn",
                      [f"Content looks most like {names[predicted]} ({round(probability * 100)}%), "
                       f"{names[selected]} is less likely ({round(selected_probability * 100)}%)."],
                      extra=extra)
    return _layer("classification", "Document classification", "fail",
                  [f"You selected {names[selected]}, but the content looks like {names[predicted]} "
                   f"({round(probability * 100)}% confidence)."], extra=extra)


def structure_layer(document_type, fields):
    required = DOCUMENT_TYPES[document_type]["required"]
    present = [f for f in required if fields.get(f)]
    missing = [f for f in required if not fields.get(f)]
    details = [f"{FIELD_LABELS[f]}: present" for f in present] + [f"{FIELD_LABELS[f]}: missing" for f in missing]
    if document_type.startswith("marksheet") and fields.get("subjects"):
        details.append(f"{len(fields['subjects'])} subject rows found in the marks table.")
    ratio = len(present) / len(required)
    status = "pass" if not missing else "warn" if ratio >= 0.6 else "fail"
    return _layer("structure", "Structure & required fields", status, details,
                  extra={"present": len(present), "required": len(required)})


def consistency_layer(document_type, fields):
    findings = consistency.check(document_type, fields)
    details = [p["message"] for p in findings.problems] + findings.passed
    if not findings.problems and not findings.passed:
        return _layer("consistency", "Data consistency", "skipped",
                      ["No values were found that can be cross-checked."])
    if any(p["severity"] == "fail" for p in findings.problems):
        return _layer("consistency", "Data consistency", "fail", details, critical=True)
    if findings.problems:
        details.append("These differences involve low-confidence OCR readings and may be misreads.")
        return _layer("consistency", "Data consistency", "warn", details)
    return _layer("consistency", "Data consistency", "pass", details)


def tampering_layer(colour_pages, result, file_bytes, extension, metadata):
    analysis = tamper.analyse(colour_pages[0], result.lines, file_bytes, extension, metadata)
    details = list(analysis["metadataFindings"])
    for value in analysis["suspiciousValues"]:
        details.append(f"Printed value \"{value['text']}\" differs from the values around it in "
                       f"{' and '.join(value['reasons'])}.")
    extra = {"heatmap": analysis["heatmap"], "suspiciousValues": analysis["suspiciousValues"]}
    editing_tool = any("edited with" in f or "editing software" in f for f in analysis["metadataFindings"])
    if analysis["suspiciousValues"] or editing_tool:
        return _layer("tampering", "Tampering analysis", "fail", details, extra=extra)
    if analysis["metadataFindings"]:
        return _layer("tampering", "Tampering analysis", "warn", details, extra=extra)
    if analysis["valuesCompared"] >= 8:
        details.append(f"{analysis['valuesCompared']} printed values compared for size, ink and background: "
                       "none stand out.")
    else:
        details.append("File metadata shows no editing software. Too few printed values to compare "
                       "their print characteristics.")
    return _layer("tampering", "Tampering analysis", "pass", details, extra=extra)


def qr_layer(colour_pages, fields, document_type):
    payload = qr.decode(colour_pages)
    check = qr.verify(payload, fields, document_type)
    extra = {"qrFound": check["found"], "qrPreview": check["payloadPreview"]}
    if not check["found"]:
        return _layer("qr", "QR code / document ID", "skipped", ["No readable QR code on this document."],
                      extra=extra)
    details = check["problems"] + check["passed"] + check["neutral"]
    if check["problems"]:
        return _layer("qr", "QR code / document ID", "fail", details, critical=True, extra=extra)
    if check["passed"]:
        return _layer("qr", "QR code / document ID", "pass", details, extra=extra)
    return _layer("qr", "QR code / document ID", "skipped", details, extra=extra)


COMPARED_FIELDS = ("name", "rollNumber", "applicationNumber", "certificateNumber", "aadhaarNumber",
                   "dateOfBirth", "fatherName", "motherName", "result", "totalPercentile", "cgpa",
                   "percentage", "grandTotal", "issueDate")


def _compare_fields(expected, fields, source):
    """Compare trusted values (a record or a genuine reference) with the document's values.

    `expected` maps field names to values; its "subjects" entry maps subject name to total.
    """
    problems, passed = [], []
    for key, value in expected.items():
        if key == "subjects" and isinstance(value, dict):
            rows = {r["subject"]: r for r in fields.get("subjects", [])}
            for subject, total in value.items():
                match = max(rows, key=lambda s: similarity(s, subject), default=None)
                if match is None or similarity(match, subject) < 0.7 or rows[match]["total"] is None:
                    continue
                if rows[match]["total"] == int(total):
                    passed.append(f"{subject.title()} total {total} matches the {source}.")
                else:
                    problems.append(f"{subject.title()}: document shows {rows[match]['total']}, "
                                    f"{source} shows {total}.")
            continue
        actual = fields.get(key)
        if actual in (None, "") or value in (None, ""):
            continue
        label = FIELD_LABELS.get(key, key)
        same = (similarity(str(actual), str(value)) >= 0.85 if key.endswith("ame")
                else normalized_text(str(actual)) == normalized_text(str(value)))
        if same:
            passed.append(f"{label} matches the {source}.")
        else:
            problems.append(f"{label} differs: document says {actual}, {source} says {str(value).upper()}.")
    return problems, passed


def _trusted_values(fields):
    values = {k: fields[k] for k in COMPARED_FIELDS if fields.get(k)}
    if fields.get("subjects"):
        values["subjects"] = {r["subject"]: r["total"] for r in fields["subjects"] if r["total"] is not None}
    return values


def records_layer(document_type, fields, records):
    if not records:
        return _layer("records", "Authorized record check", "skipped",
                      ["No authorized records are configured for this document type."])
    identifiers = {normalized_text(str(fields[k])) for k in DOCUMENT_TYPES[document_type]["identifiers"]
                   if fields.get(k)}
    if not identifiers:
        return _layer("records", "Authorized record check", "warn",
                      ["No roll number or certificate ID could be read to look up an authorized record."])
    record = next((r for r in records if normalized_text(r.identifier) in identifiers), None)
    if record is None:
        return _layer("records", "Authorized record check", "warn",
                      [f"No authorized record exists for {', '.join(sorted(identifiers))}."])
    expected = {"name": record.name, **record.fields}
    problems, passed = _compare_fields(expected, fields, "record")
    source = f" ({record.source})" if record.source else ""
    details = [f"Found authorized record {record.identifier}{source}."] + problems + passed
    if problems:
        return _layer("records", "Authorized record check", "fail", details, critical=True)
    return _layer("records", "Authorized record check", "pass", details)


def reference_layer(document_type, result, fields, reference_root):
    """Compare with genuine references: field by field for the same record, otherwise by text."""
    paths = list_references(reference_root, document_type)
    if not paths:
        return _layer("reference", "Reference document comparison", "skipped",
                      ["No genuine reference documents are configured for this type."])
    submitted = normalized_text(result.text)
    identifiers = [normalized_text(str(fields[k])) for k in DOCUMENT_TYPES[document_type]["identifiers"]
                   if fields.get(k)]
    best, same_record = 0.0, None
    for path in paths:
        text = reference_text(path)
        normalized = normalized_text(text)
        if len(normalized) < MIN_TEXT_LENGTH:
            continue
        score = SequenceMatcher(None, submitted, normalized, autojunk=False).ratio()
        best = max(best, score)
        if identifiers and any(i and i in normalized for i in identifiers):
            same_record = (score, text)
    extra = {"similarity": round(best, 4)}

    if same_record:
        score, text = same_record
        extra["similarity"] = round(score, 4)
        reference_fields, _ = extract.extract_fields(document_type, ocr.from_text(text))
        problems, passed = _compare_fields(_trusted_values(reference_fields), fields, "genuine reference")
        summary = f"Found a genuine reference for the same record ({score * 100:.1f}% text similarity)."
        if problems:
            return _layer("reference", "Reference document comparison", "fail",
                          [summary] + problems + passed, critical=True, extra=extra)
        return _layer("reference", "Reference document comparison", "pass", [summary] + passed, extra=extra)
    if best >= MATCH_THRESHOLD:
        return _layer("reference", "Reference document comparison", "pass",
                      [f"Text matches a genuine reference document ({best * 100:.1f}% similar)."], extra=extra)
    return _layer("reference", "Reference document comparison", "skipped",
                  [f"No genuine reference for this record (closest reference is {best * 100:.1f}% similar)."],
                  extra=extra)


# ---------------------------------------------------------------- engine

def score(layers):
    evaluated = [l for l in layers if l["status"] in STATUS_RISK]
    total_weight = sum(WEIGHTS.values())
    used_weight = sum(l["weight"] for l in evaluated)
    risk = round(100 * sum(l["weight"] * STATUS_RISK[l["status"]] for l in evaluated) / used_weight) \
        if used_weight else 100
    coverage = used_weight / total_weight
    by_key = {l["key"]: l for l in layers}

    if by_key["ocr"]["status"] == "fail":
        verdict = "review"
    elif any(l["critical"] and l["status"] == "fail" for l in layers):
        verdict = "suspicious"
        risk = max(risk, 70)
    elif risk >= SUSPICIOUS_AT:
        verdict = "suspicious"
    elif risk >= REVIEW_AT or coverage < MIN_COVERAGE or by_key["structure"]["status"] == "fail":
        verdict = "review"
    else:
        verdict = "verified"
    return verdict, risk, round(coverage, 2)


def run(document_type, file_bytes, extension, filename, reference_root, records):
    result, colour_pages, steps, metadata = read_document(file_bytes, extension)
    fields, field_confidence = extract.extract_fields(document_type, result)

    layers = [ocr_layer(result)]
    if layers[0]["status"] != "fail":
        reference_texts = cached_reference_texts(reference_root)
        layers += [
            classification_layer(document_type, result.text, reference_texts),
            structure_layer(document_type, fields),
            consistency_layer(document_type, fields),
            tampering_layer(colour_pages, result, file_bytes, extension, metadata),
            qr_layer(colour_pages, fields, document_type),
            records_layer(document_type, fields, records),
            reference_layer(document_type, result, fields, reference_root),
        ]
    else:
        layers += [_layer(key, name, "skipped", ["Skipped because the text could not be read."])
                   for key, name in (("classification", "Document classification"),
                                     ("structure", "Structure & required fields"),
                                     ("consistency", "Data consistency"),
                                     ("tampering", "Tampering analysis"),
                                     ("qr", "QR code / document ID"),
                                     ("records", "Authorized record check"),
                                     ("reference", "Reference document comparison"))]

    verdict, risk, coverage = score(layers)
    label, message = VERDICTS[verdict]
    reasons = [
        {"status": layer["status"], "text": layer["details"][0], "layer": layer["name"]}
        for layer in layers if layer["details"] and layer["status"] in ("fail", "warn")
    ] + [
        {"status": "pass", "text": f"{layer['name']} passed", "layer": layer["name"]}
        for layer in layers if layer["status"] == "pass"
    ]

    subjects = fields.pop("subjects", [])
    return {
        "documentType": document_type,
        "documentTypeName": DOCUMENT_TYPES[document_type]["name"],
        "filename": filename,
        "verdict": verdict,
        "verdictLabel": label,
        "message": message,
        "riskScore": risk,
        "coverage": coverage,
        "reasons": reasons,
        "layers": layers,
        "fields": [
            {"key": key, "label": FIELD_LABELS.get(key, key), "value": value,
             "confidence": field_confidence.get(key)}
            for key, value in fields.items()
        ],
        "subjects": [{k: v for k, v in row.items() if k != "tokens"} for row in subjects],
        "preprocessing": steps or ["Image was already clean: no corrections needed."],
        "ocrText": result.text[:6000],
        "disclaimer": "This is an automated assessment to support a human verifier. It is not proof of "
                      "official authenticity.",
    }
