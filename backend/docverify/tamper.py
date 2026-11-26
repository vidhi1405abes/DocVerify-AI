"""Tampering detection: printed-value consistency and file metadata.

Edited marks, totals or IDs are usually typed or pasted over the original print, so they
rarely match the size, baseline, ink and paper colour of the surrounding values printed
in the same table. Each value is compared with its peers, and outliers are reported.
"""

import base64
import io
import re

import cv2
import numpy as np
from PIL import Image

EDITING_TOOLS = re.compile(
    r"photoshop|gimp|paint\.net|canva|pixlr|snapseed|picsart|illustrator|coreldraw|"
    r"affinity|inkscape|pdfescape|sejda|smallpdf|ilovepdf|pdf-?xchange|foxit phantom|"
    r"nitro|pdfelement|acrobat pro|photopea|fotor",
    re.IGNORECASE,
)
VALUE_TOKEN = re.compile(r"^[0-9OoIl]{2,3}$|^\d{1,2}\.\d{1,2}$")
MIN_VALUES = 8
OUTLIER_SPREADS = 4.5

# Feature name, human description, minimum absolute difference that matters.
FEATURES = [
    ("height", "text size", 0.3),
    ("baseline", "baseline position", 0.35),
    ("ink", "ink darkness", 25.0),
    ("paper", "paper shade behind it", 6.0),
    ("tint", "paper tint", 3.0),
    ("stroke", "stroke thickness", 0.1),
]
LIGHTING_FEATURES = ("ink", "paper", "tint")


def _token_features(image_lab, word, row_height):
    x0, y0, x1, y1 = max(word.x0, 0), max(word.y0, 0), word.x1, word.y1
    patch = image_lab[y0:y1, x0:x1]
    if patch.size == 0 or patch.shape[0] < 4 or patch.shape[1] < 4:
        return None
    lightness = np.ascontiguousarray(patch[:, :, 0])
    threshold = cv2.threshold(lightness, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0]
    ink = lightness <= threshold
    if ink.sum() < 5 or (~ink).sum() < 5:
        return None
    paper = patch[~ink]
    return {
        "height": (y1 - y0) / row_height,
        "ink": float(np.mean(lightness[ink])),
        "paper": float(np.mean(paper[:, 0])),
        "tint": float(np.hypot(np.mean(paper[:, 1]) - 128, np.mean(paper[:, 2]) - 128)),
        "stroke": float(ink.mean()),
    }


def _nearest(samples, sample, same_key, distance_axis, count=2):
    peers = [s for s in samples if s is not sample and s[same_key] == sample[same_key]]
    return sorted(peers, key=lambda s: abs(s["center"][distance_axis] - sample["center"][distance_axis]))[:count]


def find_inconsistent_values(image, lines):
    """Compare every printed value in a table with its nearest neighbours.

    Size and baseline are compared with the rest of the row. Ink and paper shade are
    compared with the closest values above, below and beside it, so the gradual lighting
    changes of a photographed page cancel out. A value is reported only when it stands
    clearly apart from what the rest of the table shows.
    """
    image_lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    samples = []
    for row, line in enumerate(lines):
        # The first token of a table row is the subject code, printed in another column style.
        values = [w for w in line.words[1:] if VALUE_TOKEN.match(w.text)]
        if len(values) < 2:
            continue
        row_height = float(np.median([w.height for w in values])) or 1.0
        row_bottom = float(np.median([w.y1 for w in values]))
        for word in values:
            features = _token_features(image_lab, word, row_height)
            if features is None:
                continue
            features["baseline"] = (word.y1 - row_bottom) / row_height
            samples.append({
                "word": word, "row": row, "features": features,
                "center": ((word.x0 + word.x1) / 2, (word.y0 + word.y1) / 2),
            })

    if len(samples) < MIN_VALUES:
        return []

    typical_height = float(np.median([s["word"].height for s in samples]))
    columns = []
    for sample in sorted(samples, key=lambda s: s["word"].x1):
        if columns and sample["word"].x1 - columns[-1][-1]["word"].x1 < typical_height * 2:
            columns[-1].append(sample)
        else:
            columns.append([sample])
    for number, column in enumerate(columns):
        for sample in column:
            sample["column"] = number

    residuals = {name: [] for name, _, _ in FEATURES}
    for sample in samples:
        neighbours = _nearest(samples, sample, "column", 1) + _nearest(samples, sample, "row", 0)
        sample["residual"] = {}
        for name, _, _ in FEATURES:
            value = sample["features"][name]
            if name in LIGHTING_FEATURES:
                expected = float(np.median([s["features"][name] for s in neighbours])) if neighbours else value
            else:
                expected = 1.0 if name == "height" else 0.0
            sample["residual"][name] = value - expected
            residuals[name].append(value - expected)

    spreads = {
        name: max(float(np.median(np.abs(np.array(values) - np.median(values)))) * 1.4826, 1e-6)
        for name, values in residuals.items()
    }
    centres = {name: float(np.median(values)) for name, values in residuals.items()}

    flagged = []
    for sample in samples:
        reasons, strongest = [], 0.0
        for name, label, min_difference in FEATURES:
            deviation = abs(sample["residual"][name] - centres[name])
            if deviation >= min_difference and deviation > OUTLIER_SPREADS * spreads[name]:
                reasons.append(label)
                strongest = max(strongest, deviation / min_difference)
        # One weak signal is usually OCR or lighting noise; ask for two, or one strong one.
        if len(reasons) >= 2 or strongest >= 2:
            word = sample["word"]
            flagged.append({"text": word.text, "reasons": reasons,
                            "box": [word.x0, word.y0, word.x1, word.y1]})
    return flagged


def heatmap_data_url(image, boxes):
    """A downscaled copy of the page with suspicious values outlined, as a data URL."""
    marked = image.copy()
    overlay = image.copy()
    for x0, y0, x1, y1 in boxes:
        pad = max(4, (y1 - y0) // 3)
        cv2.rectangle(overlay, (x0 - pad, y0 - pad), (x1 + pad, y1 + pad), (0, 0, 255), -1)
    marked = cv2.addWeighted(overlay, 0.3, marked, 0.7, 0)
    for x0, y0, x1, y1 in boxes:
        pad = max(4, (y1 - y0) // 3)
        cv2.rectangle(marked, (x0 - pad, y0 - pad), (x1 + pad, y1 + pad), (0, 0, 255), 2)
    scale = min(1.0, 1000 / max(marked.shape[:2]))
    if scale < 1:
        marked = cv2.resize(marked, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", marked, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode() if ok else None


def image_metadata_findings(file_bytes):
    try:
        with Image.open(io.BytesIO(file_bytes)) as image:
            software = str(image.getexif().get(0x0131, "") or image.info.get("Software", ""))
    except Exception:
        return []
    if software and EDITING_TOOLS.search(software):
        return [f"Image metadata says it was saved by editing software ({software.strip()})."]
    return []


def pdf_metadata_findings(metadata, signed=False):
    findings = []
    producer = " ".join(str(metadata.get(key, "")) for key in ("Producer", "Creator")).strip()
    match = EDITING_TOOLS.search(producer)
    if match:
        findings.append(f"PDF was produced or edited with {match.group(0)} ({producer}).")
    created = str(metadata.get("CreationDate", ""))[:16]
    modified = str(metadata.get("ModDate", ""))[:16]
    # Signing a PDF (DigiLocker, e-Aadhaar) changes its modification date, so that is expected.
    if created and modified and created != modified and not signed:
        findings.append("PDF was modified after it was first created.")
    return findings


def analyse(color_page, lines, file_bytes, extension, pdf_metadata, signed=False):
    metadata_findings = (
        pdf_metadata_findings(pdf_metadata, signed) if extension == ".pdf" else image_metadata_findings(file_bytes)
    )
    first_page_lines = [line for line in lines if line.page == 0]
    values = find_inconsistent_values(color_page, first_page_lines)
    return {
        "metadataFindings": metadata_findings,
        "suspiciousValues": [{"text": v["text"], "reasons": v["reasons"]} for v in values],
        "heatmap": heatmap_data_url(color_page, [v["box"] for v in values]) if values else None,
        "valuesCompared": sum(
            1 for line in first_page_lines for w in line.words if VALUE_TOKEN.match(w.text)
        ),
    }
