"""QR code decoding and verification (certificate links and Aadhaar secure QR)."""

import gzip
import re
from urllib.parse import urlparse

import cv2

from .textutils import similarity

OFFICIAL_DOMAINS = (
    "gov.in", "nic.in", "cbse.gov.in", "digilocker.gov.in", "nta.ac.in", "uidai.gov.in",
    "results.cbse.nic.in", "jeemain.nta.ac.in", "ac.in", "edu.in",
)
SECURE_QR_FIELDS = [
    "emailMobileIndicator", "referenceId", "name", "dateOfBirth", "gender", "careOf", "district",
    "landmark", "house", "location", "pincode", "postOffice", "state", "street", "subDistrict", "vtc",
]


def decode(images):
    """Try to decode a QR code on any page, at a few scales."""
    detector = cv2.QRCodeDetector()
    for image in images:
        for scale in (1.0, 2.0, 0.5):
            candidate = image if scale == 1.0 else cv2.resize(image, None, fx=scale, fy=scale)
            try:
                payload, points, _ = detector.detectAndDecode(candidate)
            except cv2.error:
                continue
            if payload:
                return payload
    return None


def decode_aadhaar_secure_qr(payload):
    """UIDAI secure QR: a big decimal number holding gzip data with 0xFF-separated fields."""
    if not payload.isdigit() or len(payload) < 200:
        return None
    number = int(payload)
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
    try:
        data = gzip.decompress(raw)
    except OSError:
        return None
    parts = data.split(b"\xff")
    # Version-2 codes start with a version marker such as "V2".
    if parts and parts[0][:1] == b"V":
        parts = parts[1:]
    values = [part.decode("iso-8859-1", errors="replace") for part in parts[: len(SECURE_QR_FIELDS)]]
    return dict(zip(SECURE_QR_FIELDS, values))


def _iso_from_ddmmyyyy(value):
    match = re.match(r"(\d{2})[-/](\d{2})[-/](\d{4})$", value or "")
    return f"{match.group(3)}-{match.group(2)}-{match.group(1)}" if match else None


def verify(payload, fields, document_type):
    """Compare QR contents with what OCR read from the document."""
    result = {"found": payload is not None, "payloadPreview": None, "passed": [], "problems": [],
              "neutral": []}
    if payload is None:
        return result
    result["payloadPreview"] = payload[:160] + ("..." if len(payload) > 160 else "")

    if document_type == "aadhaar":
        decoded = decode_aadhaar_secure_qr(payload)
        if decoded is None and "<PrintLetterBarcodeData" in payload:
            decoded = dict(re.findall(r'(\w+)="([^"]*)"', payload))
            decoded["dateOfBirth"] = decoded.get("dob", decoded.get("yob", ""))
        if decoded:
            result["payloadPreview"] = "Aadhaar QR data decoded (signature not verified offline)."
            qr_name = decoded.get("name", "")
            if fields.get("name") and qr_name:
                if similarity(qr_name, fields["name"]) >= 0.8:
                    result["passed"].append("Name in the QR code matches the printed name.")
                else:
                    result["problems"].append(
                        f"Name in the QR code ({qr_name}) differs from the printed name ({fields['name']}).")
            qr_dob = _iso_from_ddmmyyyy(decoded.get("dateOfBirth", "")) or decoded.get("dateOfBirth")
            if fields.get("dateOfBirth") and qr_dob:
                same_year_only = len(qr_dob) == 4 and qr_dob == fields["dateOfBirth"][:4]
                if qr_dob == fields["dateOfBirth"] or same_year_only:
                    result["passed"].append("Date of birth in the QR code matches the printed date.")
                else:
                    result["problems"].append("Date of birth in the QR code differs from the printed date.")
            qr_gender = decoded.get("gender", "")[:1].upper()
            if fields.get("gender") and qr_gender:
                if qr_gender == fields["gender"][:1]:
                    result["passed"].append("Gender in the QR code matches the printed gender.")
                else:
                    result["problems"].append("Gender in the QR code differs from the printed gender.")
            return result

    url = re.search(r"https?://\S+", payload)
    if url:
        host = (urlparse(url.group(0)).hostname or "").lower()
        if any(host == domain or host.endswith("." + domain) for domain in OFFICIAL_DOMAINS):
            result["passed"].append(f"QR code links to an official domain ({host}).")
        else:
            result["problems"].append(
                f"QR code links to {host}, which is not an official government or education domain.")

    compact = re.sub(r"\s", "", payload).upper()
    for key, label in (("rollNumber", "roll number"), ("certificateNumber", "certificate number"),
                       ("applicationNumber", "application number"), ("serialNumber", "serial number")):
        if fields.get(key):
            if fields[key] in compact:
                result["passed"].append(f"QR code contains the printed {label}.")
            elif not url:
                result["problems"].append(f"QR code does not contain the printed {label} ({fields[key]}).")
    if fields.get("name") and not url:
        if re.sub(r"\s", "", fields["name"]) in compact:
            result["passed"].append("QR code contains the printed name.")
    if not result["passed"] and not result["problems"]:
        result["neutral"].append("QR code was read, but it holds nothing that can be matched to this document.")
    return result
