import io

import numpy as np
from PIL import Image

from docverify.ocr import Line, OcrResult, Word


def make_pdf():
    pdf = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(pdf, format="PDF")
    return pdf.getvalue()


def make_png():
    image = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(image, format="PNG")
    return image.getvalue()


def fake_ocr(text, confidence=0.99):
    """An OCR result where every whitespace-separated token is one word box."""
    lines = []
    for row, raw in enumerate(line for line in text.strip().splitlines() if line.strip()):
        words, x = [], 10
        for token in raw.split():
            width = 12 * len(token)
            words.append(Word(token, confidence, x, 20 + row * 30, x + width, 40 + row * 30))
            x += width + 12
        lines.append(Line(words, 0))
    return OcrResult(lines=lines, mean_confidence=confidence, word_count=sum(len(l.words) for l in lines))


def fake_read_document(text, confidence=0.99):
    page = np.full((600, 800, 3), 255, dtype=np.uint8)

    def read_document(_file_bytes, _extension):
        return fake_ocr(text, confidence), [page], [], {}

    return read_document


GENUINE_MARKSHEET = """
CENTRAL BOARD OF SECONDARY EDUCATION
MARKS STATEMENT CUM CERTIFICATE
SECONDARY SCHOOL EXAMINATION, 2020
This is to certify that VAIBHAV KUMAR
Roll No. 25147975
Mother's Name ASHA RANI
Father's / Guardian's Name ANUJ KUMAR
Date of Birth 08-05-2004 8TH MAY TWO THOUSAND FOUR
School 81270 SAI MILLENIUM SCHOOL
SUB CODE SUBJECT THEORY PR TOTAL TOTAL (IN WORDS) GRADE
184 ENGLISH LANG LIT 077 020 097 NINETY SEVEN A1
002 HINDI COURSE-A 079 020 099 NINETY NINE A1
041 MATHEMATICS STANDARD 080 020 100 ONE HUNDRED A1
086 SCIENCE 075 020 095 NINETY FIVE A1
087 SOCIAL SCIENCE 077 020 097 NINETY SEVEN A1
Result PASS
Dated 15-07-2020 Controller of Examinations
"""

# Mathematics total changed from 100 to 090: no longer matches 80 + 20 or "ONE HUNDRED".
TAMPERED_MARKSHEET = GENUINE_MARKSHEET.replace("080 020 100 ONE HUNDRED", "080 020 090 ONE HUNDRED")
