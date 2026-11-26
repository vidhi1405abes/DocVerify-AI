"""The verification engine: runs every layer and combines them into an explainable verdict."""

import threading
from difflib import SequenceMatcher
from pathlib import Path

from . import classify, consistency, extract, ocr, qr, tamper
from .config import SUPPORTED_EXTENSIONS
from .doc_types import DOCUMENT_TYPES, FIELD_LABELS, required_label, required_present
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
    "history": 10,
}
STATUS_RISK = {"pass": 0.0, "warn": 0.5, "fail": 1.0}
SUSPICIOUS_AT = 55
REVIEW_AT = 25
MIN_COVERAGE = 0.4
MATCH_THRESHOLD = 0.9
MIN_TEXT_LENGTH = 30
SUSPICIOUS_MIN_RISK = 70
REJECTED_MIN_RISK = 90
WRONG_TYPE_CONFIDENCE = 0.6
NOT_A_DOCUMENT_CONFIDENCE = 0.5

VERDICTS = {
    "verified": ("Verified", "Most verification checks passed and no signs of manipulation were found."),
    "review": ("Requires Review", "The system could not confidently verify this document. A person should "
                                  "inspect it."),
    "suspicious": ("Suspicious", "Checks point to manipulation, inconsistent data, the wrong document type or "
                                 "a record mismatch."),
    "rejected": ("Rejected", "The document cannot be accepted: mandatory information is missing, it could not "
                             "be read, or it is not a supported document."),
}

_ocr_lock = threading.Lock()


def _layer(key, name, status, details, critical=False, extra=None):
    layer = {"key": key, "name": name, "status": status, "details": details, "weight": WEIGHTS[key],
             "critical": critical}
    if extra:
        layer.update(extra)
    return layer


def read_document(file_bytes, extension, password=None):
    """Load, preprocess and read a document. Returns (ocr result, colour pages, steps, pdf metadata).

    A digital PDF (e.g. from DigiLocker) is read from its embedded text: exact, with no OCR.
    """
    pages, metadata, embedded = ocr.load_pages(file_bytes, extension, password)
    if embedded:
        result = ocr.from_text(embedded)
        result.digital = True
        steps = ["Read the digital text embedded in the PDF (exact, no OCR needed)"]
        return result, pages, steps, metadata
    result, colours, steps = ocr.OcrResult(), [], []
    confidences = []
    tips = ocr.photo_quality_tips(pages[0])
    for index, page in enumerate(pages):
        gray, colour, page_steps = ocr.preprocess(page)
        with _ocr_lock:
            page_result = ocr.read_text([gray], index)
            # Blurry or shadowed photos get a second, stronger clean-up; keep whichever reads better.
            if ocr.needs_enhancement(page_result):
                enhanced_gray, enhanced_colour, enhanced_steps = ocr.enhance(gray, colour)
                enhanced_result = ocr.read_text([enhanced_gray], index)
                if ocr.reading_quality(enhanced_result) > ocr.reading_quality(page_result):
                    page_result, colour = enhanced_result, enhanced_colour
                    page_steps = page_steps + enhanced_steps
        colours.append(colour)
        steps.extend(step for step in page_steps if step not in steps)
        result.lines.extend(page_result.lines)
        confidences += [w.conf for line in page_result.lines for w in line.words]
    result.word_count = len(confidences)
    result.mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    result.photo_tips = tips
    return result, colours, steps, metadata


def reference_text(path):
    """OCR text of a stored reference document, cached next to it."""
    cache = path.with_name(path.name + ".txt")
    if cache.exists():
        return cache.read_text(encoding="utf8")
    try:
        result, _, _, _ = read_document(path.read_bytes(), path.suffix.lower())  # password PDFs: skipped
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
                      ["Too little text could be read. Upload a clearer, straight-on scan or photo."],
                      extra={"rejection": "The document is blank or unreadable."})
    confidence = round(result.mean_confidence * 100)
    details = [f"Read {result.word_count} text regions with {confidence}% average OCR confidence."]
    if result.mean_confidence < 0.35:
        details.append("Low OCR confidence: some values may be misread.")
        return _layer("ocr", "Text extraction (OCR)", "warn", details)
    return _layer("ocr", "Text extraction (OCR)", "pass", details)


def classification_layer(selected, text, reference_texts, fields):
    """Is this the type of document the user said it is?

    Explicit wording ("Senior School Certificate Examination") or subjects decide 10th versus
    12th; otherwise the scikit-learn model decides. A different type is a critical failure.
    """
    predicted, probability, ranked = classify.classify(text, reference_texts)
    selected_probability = dict(ranked).get(selected, 0.0)
    names = {k: v["name"] for k, v in DOCUMENT_TYPES.items()} | {"other": "an unrelated document"}
    extra = {"detectedType": predicted, "detectedTypeName": names[predicted],
             "probability": round(probability, 3),
             "ranking": [{"type": t, "name": names[t], "probability": p} for t, p in ranked]}
    name = "Document classification"

    evidence = classify.type_evidence(text, fields.get("subjects", []))
    if evidence:
        evidence_type, reason = evidence
        extra.update(detectedType=evidence_type, detectedTypeName=names[evidence_type])
        if evidence_type == selected:
            return _layer("classification", name, "pass",
                          [f"This is a {names[selected]}: {reason}."], extra=extra)
        return _layer("classification", name, "fail",
                      [f"Wrong document type: you selected {names[selected]}, but this is a "
                       f"{names[evidence_type]} ({reason})."], critical=True, extra=extra)

    if predicted == selected:
        return _layer("classification", name, "pass",
                      [f"Content matches a {names[selected]} ({round(probability * 100)}% confidence)."],
                      extra=extra)
    if predicted == classify.OTHER:
        if probability >= NOT_A_DOCUMENT_CONFIDENCE:
            extra["rejection"] = "It does not look like any supported document."
            return _layer("classification", name, "fail",
                          [f"This does not look like a {names[selected]} or any other supported document "
                           f"({round(probability * 100)}% confidence)."], extra=extra)
        # Too little readable text to tell: that is uncertainty, not a different document type.
        return _layer("classification", name, "warn",
                      [f"Could not confirm this is a {names[selected]}: too little readable text. "
                       "A clearer photo or scan will help."], extra=extra)
    if probability >= WRONG_TYPE_CONFIDENCE or selected_probability < 0.2:
        return _layer("classification", name, "fail",
                      [f"Wrong document type: you selected {names[selected]}, but the content looks like "
                       f"{names[predicted]} ({round(probability * 100)}% confidence)."],
                      critical=True, extra=extra)
    return _layer("classification", name, "warn",
                  [f"Content looks most like {names[predicted]} ({round(probability * 100)}%), "
                   f"{names[selected]} is less likely ({round(selected_probability * 100)}%)."], extra=extra)


def structure_layer(document_type, fields):
    required = DOCUMENT_TYPES[document_type]["required"]
    present = [f for f in required if required_present(f, fields)]
    missing = [f for f in required if not required_present(f, fields)]
    details = ([f"{required_label(f)}: present" for f in present]
               + [f"{required_label(f)}: missing" for f in missing])
    if document_type.startswith("marksheet") and fields.get("subjects"):
        details.append(f"{len(fields['subjects'])} subject rows found in the marks table.")
    extra = {"present": len(present), "required": len(required), "missing": [required_label(f) for f in missing]}
    if not missing:
        if document_type == "domicile" and not fields.get("certificateNumber"):
            details.insert(0, "This is an application for a domicile certificate, not the issued certificate: "
                              "it has an application number but no certificate number.")
            return _layer("structure", "Structure & required fields", "warn", details, extra=extra)
        return _layer("structure", "Structure & required fields", "pass", details, extra=extra)
    missing_labels = ", ".join(required_label(f) for f in missing)
    extra["rejection"] = f"Mandatory field(s) missing: {missing_labels}."
    details.insert(0, f"Mandatory field(s) missing: {missing_labels}. If they are printed on the document, "
                      "upload a clearer scan.")
    return _layer("structure", "Structure & required fields", "fail", details, extra=extra)


def _stored_values(result):
    """Field values and subject totals saved with an earlier verification."""
    values = {f["key"]: f["value"] for f in result.get("fields", []) if f["key"] in COMPARED_FIELDS}
    subjects = {r["subject"]: r["total"] for r in result.get("subjects", []) if r.get("total") is not None}
    if subjects:
        values["subjects"] = subjects
    return values


def history_layer(document_type, fields, previous):
    """Has this roll / certificate number been verified before with different details?

    A forged copy usually reuses a genuine ID with a different name or changed marks.
    """
    keys = [k for k in DOCUMENT_TYPES[document_type]["identifiers"] if fields.get(k)]
    if not keys:
        return _layer("history", "Previous verifications", "skipped",
                      ["No roll or certificate number to compare with earlier verifications."])
    matches = []
    for earlier in previous or []:
        values = _stored_values(earlier)
        if any(normalized_text(str(values.get(k, ""))) == normalized_text(str(fields[k])) for k in keys):
            matches.append((earlier, values))
    if not matches:
        return _layer("history", "Previous verifications", "skipped",
                      ["This ID has not been verified before."])

    for earlier, values in matches:
        problems, passed = _compare_fields(values, fields, "earlier verification")
        if problems:
            when = earlier.get("createdAt", "")[:10]
            identifier = fields[keys[0]]
            details = [f"{FIELD_LABELS[keys[0]]} {identifier} was verified on {when} with different details."]
            return _layer("history", "Previous verifications", "fail", details + problems, critical=True)
    return _layer("history", "Previous verifications", "pass",
                  [f"Matches {len(matches)} earlier verified document(s) with the same ID."])


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
    signed = extension == ".pdf" and ocr.has_digital_signature(file_bytes)
    # Print-style comparison needs OCR boxes; text read from a digital PDF has none.
    lines = [] if result.digital else result.lines
    analysis = tamper.analyse(colour_pages[0], lines, file_bytes, extension, metadata, signed=signed)
    details = list(analysis["metadataFindings"])
    if signed:
        details.append("The PDF carries a digital signature (as DigiLocker and e-Aadhaar PDFs do). "
                       "The signing certificate is not validated offline.")
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
    elif result.digital:
        details.append("File metadata shows no editing software.")
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
    # With the wrong type selected, that type's missing fields are a symptom, not the finding.
    wrong_type = by_key["classification"]["critical"] and by_key["classification"]["status"] == "fail"
    rejections = [l["rejection"] for l in layers
                  if l.get("rejection") and not (wrong_type and l["key"] == "structure")]

    if rejections:
        verdict, risk = "rejected", max(risk, REJECTED_MIN_RISK)
    elif any(l["critical"] and l["status"] == "fail" for l in layers):
        verdict, risk = "suspicious", max(risk, SUSPICIOUS_MIN_RISK)
    elif risk >= SUSPICIOUS_AT:
        verdict = "suspicious"
    elif risk >= REVIEW_AT or coverage < MIN_COVERAGE:
        verdict = "review"
    else:
        verdict = "verified"
    return verdict, risk, round(coverage, 2), rejections


def run(document_type, file_bytes, extension, filename, reference_root, records, previous=None,
        password=None):
    """Verify one document. `previous` holds earlier verified results of the same type."""
    result, colour_pages, steps, metadata = read_document(file_bytes, extension, password)
    fields, field_confidence = extract.extract_fields(document_type, result)

    layers = [ocr_layer(result)]
    if layers[0]["status"] != "fail":
        reference_texts = cached_reference_texts(reference_root)
        layers += [
            classification_layer(document_type, result.text, reference_texts, fields),
            structure_layer(document_type, fields),
            consistency_layer(document_type, fields),
            tampering_layer(colour_pages, result, file_bytes, extension, metadata),
            qr_layer(colour_pages, fields, document_type),
            records_layer(document_type, fields, records),
            reference_layer(document_type, result, fields, reference_root),
            history_layer(document_type, fields, previous),
        ]
    else:
        layers += [_layer(key, name, "skipped", ["Skipped because the text could not be read."])
                   for key, name in (("classification", "Document classification"),
                                     ("structure", "Structure & required fields"),
                                     ("consistency", "Data consistency"),
                                     ("tampering", "Tampering analysis"),
                                     ("qr", "QR code / document ID"),
                                     ("records", "Authorized record check"),
                                     ("reference", "Reference document comparison"),
                                     ("history", "Previous verifications"))]

    verdict, risk, coverage, rejections = score(layers)
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
        "rejectionReasons": rejections,
        "reasons": reasons,
        "layers": layers,
        "fields": [
            {"key": key, "label": FIELD_LABELS.get(key, key), "value": value,
             "confidence": field_confidence.get(key)}
            for key, value in fields.items()
        ],
        "subjects": [{k: v for k, v in row.items() if k != "tokens"} for row in subjects],
        "preprocessing": steps or ["Image was already clean: no corrections needed."],
        # Advice on retaking the photo, shown only when the reading actually struggled.
        "photoTips": result.photo_tips if (ocr.needs_enhancement(result) or rejections) else [],
        "ocrText": result.text[:6000],
        "disclaimer": "This is an automated assessment to support a human verifier. It is not proof of "
                      "official authenticity.",
    }
