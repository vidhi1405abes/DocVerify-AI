"""Document loading, image preprocessing and OCR (EasyOCR)."""

import re
import threading
from dataclasses import dataclass, field

import cv2
import numpy as np
import pypdfium2 as pdfium

from .config import MAX_PDF_PAGES
from .textutils import ascii_digits

# Indian documents mix Hindi and English. The English model reads English best and fastest,
# so it reads every text region first; regions it cannot read confidently (usually Hindi)
# are read again by the Devanagari model, and the more confident reading is kept.
HINDI_RETRY_BELOW = 0.5
SMALL_IMAGE_SIDE = 1000
SMALL_IMAGE_TARGET = 1600
DETECTION_SETTINGS = {}

_readers = {}
_reader_lock = threading.Lock()
hindi_unavailable_reason = None


def get_reader():
    with _reader_lock:
        if "en" not in _readers:
            import easyocr

            _readers["en"] = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _readers["en"]


def get_hindi_reader():
    """The Devanagari recogniser (downloaded on first use), or None if it cannot be loaded."""
    global hindi_unavailable_reason
    with _reader_lock:
        if "hi" not in _readers:
            try:
                import easyocr

                _readers["hi"] = easyocr.Reader(["hi", "en"], gpu=False, verbose=False, detector=False)
            except Exception as error:  # e.g. no internet for the first download
                _readers["hi"] = None
                hindi_unavailable_reason = str(error)
    return _readers["hi"]


@dataclass
class Word:
    text: str
    conf: float
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def yc(self):
        return (self.y0 + self.y1) / 2

    @property
    def height(self):
        return self.y1 - self.y0


@dataclass
class Line:
    words: list
    page: int

    @property
    def text(self):
        return " ".join(word.text for word in self.words)

    @property
    def box(self):
        return (
            min(w.x0 for w in self.words), min(w.y0 for w in self.words),
            max(w.x1 for w in self.words), max(w.y1 for w in self.words),
        )


@dataclass
class OcrResult:
    lines: list = field(default_factory=list)
    mean_confidence: float = 0.0
    word_count: int = 0
    photo_tips: list = field(default_factory=list)
    digital: bool = False  # text came from a PDF's embedded text layer, not OCR

    @property
    def text(self):
        return "\n".join(line.text for line in self.lines)


def from_text(text):
    """Rebuild an OcrResult from plain text (cached references and text embedded in PDFs)."""
    lines = []
    for row, raw in enumerate(line for line in ascii_digits(text).splitlines() if line.strip()):
        words, x = [], 0
        for token in raw.split():
            words.append(Word(token, 1.0, x, row * 30, x + 10 * len(token), row * 30 + 20))
            x += 10 * len(token) + 10
        lines.append(Line(words, 0))
    return OcrResult(lines=lines, mean_confidence=1.0, word_count=sum(len(l.words) for l in lines))


class UnreadableDocument(ValueError):
    pass


class PasswordRequired(UnreadableDocument):
    pass


# A digital PDF (DigiLocker, e-Aadhaar) with at least this much embedded text is read directly.
MIN_EMBEDDED_TEXT = 80
PASSWORD_HELP = ("This PDF is password-protected. Enter its password. For e-Aadhaar it is the first 4 "
                 "letters of the name in capitals followed by the year of birth, e.g. RAHU1990.")


def _open_pdf(file_bytes, password=None):
    try:
        return pdfium.PdfDocument(file_bytes, password=password or None)
    except pdfium.PdfiumError as error:
        if "password" in str(error).lower():
            raise PasswordRequired(PASSWORD_HELP if not password else
                                   "The PDF password is incorrect. " + PASSWORD_HELP) from error
        raise UnreadableDocument("The selected file is not a readable PDF.") from error


def load_pages(file_bytes, extension, password=None):
    """Return the document's page images (BGR), PDF metadata, and any text embedded in a PDF."""
    if extension == ".pdf":
        pdf = _open_pdf(file_bytes, password)
        try:
            if len(pdf) == 0:
                raise UnreadableDocument("The selected file is not a readable PDF.")
            metadata = pdf.get_metadata_dict()
            pages, texts = [], []
            for index in range(min(len(pdf), MAX_PDF_PAGES)):
                page = pdf[index]
                textpage = page.get_textpage()
                texts.append(textpage.get_text_range())
                textpage.close()
                bitmap = page.render(scale=2)
                pages.append(cv2.cvtColor(np.asarray(bitmap.to_pil().convert("RGB")), cv2.COLOR_RGB2BGR))
                bitmap.close()
                page.close()
            embedded = "\n".join(texts).replace("\r\n", "\n").replace("\r", "\n")
            if len(re.sub(r"\s", "", embedded)) < MIN_EMBEDDED_TEXT:
                embedded = ""
            return pages, metadata, embedded
        finally:
            pdf.close()

    image = cv2.imdecode(np.frombuffer(file_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise UnreadableDocument("The selected file is not a readable image.")
    return [image], {}, ""


def check_readable(file_bytes, extension, password=None):
    """Raise UnreadableDocument (or PasswordRequired) with a message if the file cannot be opened."""
    if extension != ".pdf":
        load_pages(file_bytes, extension)
        return
    pdf = _open_pdf(file_bytes, password)
    count = len(pdf)
    pdf.close()
    if count == 0:
        raise UnreadableDocument("The selected file is not a readable PDF.")


def is_readable(file_bytes, extension):
    try:
        check_readable(file_bytes, extension)
        return True
    except PasswordRequired:
        return True
    except UnreadableDocument:
        return False


def has_digital_signature(file_bytes):
    """DigiLocker and e-Aadhaar PDFs are digitally signed; a signature leaves these markers."""
    return b"/ByteRange" in file_bytes and (b"/Sig" in file_bytes or b"/adbe.pkcs7" in file_bytes)


def _estimate_skew(gray):
    """Projection-profile skew estimate in degrees (positive = counter-clockwise)."""
    small = cv2.resize(gray, None, fx=800 / max(gray.shape), fy=800 / max(gray.shape))
    binary = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    h, w = binary.shape
    center = (w / 2, h / 2)

    def score(angle):
        rotated = cv2.warpAffine(binary, cv2.getRotationMatrix2D(center, angle, 1), (w, h))
        return float(np.var(rotated.sum(axis=1)))

    best = max(np.arange(-10, 10.5, 1.0), key=score)
    return float(max(np.arange(best - 1, best + 1.01, 0.25), key=score))


def preprocess(image):
    """Upscale, straighten, denoise and boost contrast.

    Returns (gray image for OCR, colour image with the same geometry, steps applied).
    """
    steps = []
    longest = max(image.shape[:2])
    if longest < 1400:
        # Very small images (forwarded photos, thumbnails) are enlarged further so small print
        # reaches a size the text detector can find.
        factor = (SMALL_IMAGE_TARGET if longest < SMALL_IMAGE_SIDE else 1600) / longest
        image = cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        steps.append(f"Upscaled {factor:.1f}x for small text")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    angle = _estimate_skew(gray)
    if 0.5 <= abs(angle) <= 10:
        h, w = gray.shape
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
        gray = cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)
        image = cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC,
                               borderValue=(255, 255, 255))
        steps.append(f"Straightened a {abs(angle):.1f}° tilt")

    noise = float(np.std(cv2.Laplacian(gray, cv2.CV_64F)))
    if noise > 25:
        gray = cv2.fastNlMeansDenoising(gray, h=7)
        steps.append("Removed image noise")

    if float(np.std(gray)) < 55:
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        steps.append("Enhanced low contrast")

    return gray, image, steps


MAX_ENHANCED_SIDE = 3200
MIN_SHARPNESS = 60
MIN_SIDE_PIXELS = 650


def photo_quality_tips(image):
    """Plain-language advice when an upload is blurry, dark, washed out or too small."""
    tips = []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    scale = 1000 / max(gray.shape)
    sample = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if cv2.Laplacian(sample, cv2.CV_64F).var() < MIN_SHARPNESS:
        tips.append("The image is blurry. Ask the sender for a sharper photo taken with the phone held steady.")
    brightness = float(sample.mean())
    if brightness < 90:
        tips.append("The image is too dark. Ask the sender for a photo taken in daylight or a well-lit room.")
    elif brightness > 245:
        tips.append("The image is washed out by glare. Ask the sender for a photo without flash or direct light.")
    if min(image.shape[:2]) < MIN_SIDE_PIXELS:
        tips.append("The image is small, so small print is unreadable. Ask the sender to share it on WhatsApp "
                    "as a Document (not as a photo), or to send the original photo, a scan, or the DigiLocker PDF.")
    return tips


def enhance(gray, colour):
    """Stronger clean-up for blurry, shadowed or heavily compressed photos (e.g. WhatsApp images).

    Upscales 2x, flattens uneven lighting and shadows by dividing out the paper background,
    and sharpens character edges. Returns (gray, colour with the same geometry, steps).
    """
    steps = []
    factor = min(2.0, MAX_ENHANCED_SIDE / max(gray.shape[:2]))
    if factor > 1.05:
        gray = cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        colour = cv2.resize(colour, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        steps.append(f"Enhanced: upscaled {factor:.1f}x more")

    background = cv2.medianBlur(cv2.dilate(gray, np.ones((7, 7), np.uint8)), 31)
    gray = cv2.divide(gray, background, scale=255)
    steps.append("Enhanced: removed shadows and uneven lighting")

    blurred = cv2.GaussianBlur(gray, (0, 0), 1.5)
    gray = cv2.addWeighted(gray, 1.7, blurred, -0.7, 0)
    steps.append("Enhanced: sharpened blurry text")
    return gray, colour, steps


def reading_quality(result):
    """How much confidently-read text an OCR pass produced (higher is better)."""
    return sum(w.conf * len(w.text) for line in result.lines for w in line.words if w.conf >= 0.3)


def needs_enhancement(result):
    return result.mean_confidence < 0.5 or result.word_count < 30


def _group_lines(words, page):
    if not words:
        return []
    median_height = float(np.median([w.height for w in words])) or 1
    lines = []
    for word in sorted(words, key=lambda w: w.yc):
        for line in lines:
            if abs(np.mean([w.yc for w in line]) - word.yc) < median_height * 0.55:
                line.append(word)
                break
        else:
            lines.append([word])
    return [Line(sorted(line, key=lambda w: w.x0), page) for line in lines]


def _box_key(box):
    xs = [int(p[0]) for p in box]
    ys = [int(p[1]) for p in box]
    return min(xs), min(ys), max(xs), max(ys)


def _read_bilingual(image):
    """English reading of every region, with Hindi re-reading of regions English could not read."""
    reader = get_reader()
    horizontal, free = reader.detect(image, **DETECTION_SETTINGS)
    horizontal, free = horizontal[0], free[0]
    if not horizontal and not free:
        return []
    readings = reader.recognize(image, horizontal, free)

    weak = [r for r in readings if r[2] < HINDI_RETRY_BELOW]
    hindi = get_hindi_reader() if weak else None
    if hindi is None:
        return readings
    boxes = []
    for box, _, _ in weak:
        x0, y0, x1, y1 = _box_key(box)
        boxes.append([x0, x1, y0, y1])
    retried = {_box_key(box): (box, text, conf) for box, text, conf in hindi.recognize(image, boxes, [])}
    best = []
    for box, text, conf in readings:
        other = retried.get(_box_key(box))
        best.append(other if other and other[2] > conf else (box, text, conf))
    return best


def read_text(images, first_page=0):
    """OCR every page image (Hindi and English) and rebuild reading-order lines."""
    result = OcrResult()
    confidences = []
    for page_index, image in enumerate(images, start=first_page):
        words = []
        for box, text, conf in _read_bilingual(image):
            text = ascii_digits(text.strip())
            if not text:
                continue
            x0, y0, x1, y1 = _box_key(box)
            words.append(Word(text, float(conf), x0, y0, x1, y1))
            confidences.append(float(conf))
        result.lines.extend(_group_lines(words, page_index))
    result.word_count = len(confidences)
    result.mean_confidence = float(np.mean(confidences)) if confidences else 0.0
    return result
