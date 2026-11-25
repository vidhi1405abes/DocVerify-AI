"""Document loading, image preprocessing and OCR (EasyOCR)."""

import threading
from dataclasses import dataclass, field

import cv2
import numpy as np
import pypdfium2 as pdfium

from .config import MAX_PDF_PAGES

_reader = None
_reader_lock = threading.Lock()


def get_reader():
    global _reader
    with _reader_lock:
        if _reader is None:
            import easyocr

            _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


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

    @property
    def text(self):
        return "\n".join(line.text for line in self.lines)


def from_text(text):
    """Rebuild an OcrResult from plain text (used for cached reference documents)."""
    lines = []
    for row, raw in enumerate(line for line in text.splitlines() if line.strip()):
        words, x = [], 0
        for token in raw.split():
            words.append(Word(token, 1.0, x, row * 30, x + 10 * len(token), row * 30 + 20))
            x += 10 * len(token) + 10
        lines.append(Line(words, 0))
    return OcrResult(lines=lines, mean_confidence=1.0, word_count=sum(len(l.words) for l in lines))


class UnreadableDocument(ValueError):
    pass


def load_pages(file_bytes, extension):
    """Return the document as a list of BGR images (one per page) and PDF metadata."""
    if extension == ".pdf":
        try:
            pdf = pdfium.PdfDocument(file_bytes)
        except pdfium.PdfiumError as error:
            raise UnreadableDocument("The selected file is not a readable PDF.") from error
        try:
            if len(pdf) == 0:
                raise UnreadableDocument("The selected file is not a readable PDF.")
            metadata = pdf.get_metadata_dict()
            pages = []
            for index in range(min(len(pdf), MAX_PDF_PAGES)):
                page = pdf[index]
                bitmap = page.render(scale=2)
                pages.append(cv2.cvtColor(np.asarray(bitmap.to_pil().convert("RGB")), cv2.COLOR_RGB2BGR))
                bitmap.close()
                page.close()
            return pages, metadata
        finally:
            pdf.close()

    image = cv2.imdecode(np.frombuffer(file_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise UnreadableDocument("The selected file is not a readable image.")
    return [image], {}


def is_readable(file_bytes, extension):
    try:
        load_pages(file_bytes, extension) if extension != ".pdf" else _pdf_has_pages(file_bytes)
        return True
    except UnreadableDocument:
        return False


def _pdf_has_pages(file_bytes):
    try:
        pdf = pdfium.PdfDocument(file_bytes)
    except pdfium.PdfiumError as error:
        raise UnreadableDocument() from error
    count = len(pdf)
    pdf.close()
    if count == 0:
        raise UnreadableDocument()


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
        factor = 1600 / longest
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


def read_text(images):
    """OCR every page image and rebuild reading-order lines."""
    reader = get_reader()
    result = OcrResult()
    confidences = []
    for page_index, image in enumerate(images):
        words = []
        for box, text, conf in reader.readtext(image):
            text = text.strip()
            if not text:
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            words.append(Word(text, float(conf), int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))))
            confidences.append(float(conf))
        result.lines.extend(_group_lines(words, page_index))
    result.word_count = len(confidences)
    result.mean_confidence = float(np.mean(confidences)) if confidences else 0.0
    return result
