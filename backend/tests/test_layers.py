import gzip
import unittest

import cv2
import numpy as np

from docverify import classify, consistency, qr, tamper
from docverify.extract import extract_fields
from docverify.ocr import Line, Word
from docverify.textutils import parse_date, verhoeff_valid, words_to_number
from tests.helpers import GENUINE_MARKSHEET, TAMPERED_MARKSHEET, fake_ocr


class TextUtilityTests(unittest.TestCase):
    def test_words_to_number(self):
        self.assertEqual(words_to_number("SEVENTY NINE"), 79)
        self.assertEqual(words_to_number("ONE HUNDRED"), 100)
        self.assertEqual(words_to_number("NINETY"), 90)
        self.assertIsNone(words_to_number("PASS"))

    def test_parse_dates_in_figures_and_words(self):
        self.assertEqual(parse_date("08-05-2004").isoformat(), "2004-05-08")
        self.assertEqual(parse_date("9TH DECEMBER TWO THOUSAND THREE").isoformat(), "2003-12-09")
        self.assertEqual(parse_date("1ST DECEMBER NINETEEN HUNDRED NINETY").isoformat(), "1990-12-01")
        self.assertEqual(parse_date("12 May 2006").isoformat(), "2006-05-12")
        self.assertIsNone(parse_date("31-02-2004"))

    def test_verhoeff_checksum(self):
        self.assertTrue(verhoeff_valid("234123412346"))
        self.assertFalse(verhoeff_valid("234123412345"))


class ExtractionTests(unittest.TestCase):
    def test_extracts_marksheet_fields_and_subject_rows(self):
        fields, _ = extract_fields("marksheet10", fake_ocr(GENUINE_MARKSHEET))
        self.assertEqual(fields["name"], "VAIBHAV KUMAR")
        self.assertEqual(fields["motherName"], "ASHA RANI")
        self.assertEqual(fields["fatherName"], "ANUJ KUMAR")
        self.assertEqual(fields["dateOfBirthInWords"], "2004-05-08")
        self.assertEqual(fields["examYear"], 2020)
        self.assertEqual(fields["issueDate"], "2020-07-15")
        maths = next(r for r in fields["subjects"] if r["code"] == "041")
        self.assertEqual((maths["theory"], maths["practical"], maths["total"], maths["totalFromWords"]),
                         (80, 20, 100, 100))

    def test_tolerates_ocr_lookalike_characters(self):
        fields, _ = extract_fields("marksheet10", fake_ocr("Roll *o 2565OO28\n0B6 SCIENCE 'O67 {025 092 NINETY Two A1"))
        self.assertEqual(fields["rollNumber"], "25650028")
        self.assertEqual(fields["subjects"][0]["theory"], 67)

    def test_finds_name_in_badly_read_certify_line(self):
        # Real EasyOCR output from a CBSE Class XII marksheet.
        text = ("SEMOR SC HOOL ERTIFICATE EXAMINATION, 2022\nTht /e t0 cstuily Lhal Vivek KUMAR\nTTT\n"
                "Roll *o 25650028\nMuthci Name RAKHI DEVI\nFatber & Qunrdian $ Namc ARJUN KUMAR")
        fields, _ = extract_fields("marksheet12", fake_ocr(text))
        self.assertEqual(fields["name"], "VIVEK KUMAR")
        self.assertEqual(fields["fatherName"], "ARJUN KUMAR")
        self.assertEqual(fields["motherName"], "RAKHI DEVI")

    def test_extracts_aadhaar_fields(self):
        text = "Government of India\nVIDHI SHARMA\nDOB: 14/06/2001\nFEMALE\n2341 2341 2346"
        fields, _ = extract_fields("aadhaar", fake_ocr(text))
        self.assertEqual(fields["aadhaarNumber"], "234123412346")
        self.assertEqual(fields["dateOfBirth"], "2001-06-14")
        self.assertEqual(fields["gender"], "FEMALE")


class ConsistencyTests(unittest.TestCase):
    def check(self, text, document_type="marksheet10", confidence=0.99):
        fields, _ = extract_fields(document_type, fake_ocr(text, confidence))
        return consistency.check(document_type, fields)

    def test_genuine_marksheet_is_consistent(self):
        findings = self.check(GENUINE_MARKSHEET)
        self.assertEqual(findings.problems, [])
        self.assertTrue(any("add up" in p for p in findings.passed))

    def test_detects_total_that_disagrees_with_marks_and_words(self):
        findings = self.check(TAMPERED_MARKSHEET)
        self.assertEqual(findings.problems[0]["severity"], "fail")
        self.assertIn("does not match", findings.problems[0]["message"])

    def test_low_confidence_mismatch_is_only_a_warning(self):
        findings = self.check(TAMPERED_MARKSHEET, confidence=0.4)
        self.assertTrue(findings.problems)
        self.assertTrue(all(p["severity"] == "warn" for p in findings.problems))

    def test_detects_birth_date_figures_and_words_disagreeing(self):
        findings = self.check(GENUINE_MARKSHEET.replace("8TH MAY", "9TH MAY"))
        self.assertTrue(any("differs from the date in words" in p["message"] for p in findings.problems))

    def test_detects_pass_with_failing_subject(self):
        findings = self.check(GENUINE_MARKSHEET.replace("075 020 095 NINETY FIVE", "010 010 020 TWENTY"))
        self.assertTrue(any("below the pass mark" in p["message"] for p in findings.problems))

    def test_detects_fail_result_with_every_subject_passed(self):
        findings = self.check(GENUINE_MARKSHEET.replace("Result PASS", "Result FAIL"))
        self.assertTrue(any("Result says FAIL" in p["message"] for p in findings.problems))

    def test_invalid_aadhaar_checksum(self):
        findings = self.check("Government of India\nNAME\nDOB: 14/06/2001\nMALE\n2341 2341 2345", "aadhaar")
        self.assertTrue(any("Verhoeff" in p["message"] for p in findings.problems))


class ClassificationTests(unittest.TestCase):
    def test_recognises_document_types_from_noisy_text(self):
        self.assertEqual(classify.classify(GENUINE_MARKSHEET)[0], "marksheet10")
        aadhaar = "Govemment of lndia Unique ldentification Authority Aadhaar DOB MALE VID 1234"
        self.assertEqual(classify.classify(aadhaar)[0], "aadhaar")
        invoice = "INVOICE bill to quantity unit price GST subtotal amount due"
        self.assertEqual(classify.classify(invoice)[0], "other")


class ClassEvidenceTests(unittest.TestCase):
    def test_tells_tenth_and_twelfth_apart(self):
        self.assertEqual(classify.class_evidence("ALL INDIA SECONDARY SCHOOL EXAMINATION, 2019")[0], "marksheet10")
        self.assertEqual(classify.class_evidence("SENIOR SCHOOL CERTIFICATE EXAMINATION")[0], "marksheet12")
        self.assertEqual(classify.class_evidence("SEMOR SC HOOL ERTIFICATE EXAMINATION")[0], "marksheet12")
        self.assertEqual(classify.class_evidence("Senior Secondary School Examination")[0], "marksheet12")
        self.assertEqual(classify.class_evidence("Marksheet Class XII")[0], "marksheet12")
        self.assertIsNone(classify.class_evidence("Progress report Class XI"))

    def test_uses_subjects_when_wording_is_missing(self):
        self.assertEqual(classify.class_evidence("", [{"subject": "PHYSICS"}])[0], "marksheet12")
        self.assertEqual(classify.class_evidence("", [{"subject": "SOCIAL SCIENCE"}])[0], "marksheet10")


class QrTests(unittest.TestCase):
    def test_decodes_and_checks_aadhaar_secure_qr(self):
        fields = [b"V2", b"3", b"123420190101", b"VIDHI SHARMA", b"14-06-2001", b"F", b"C/O X", b"DELHI"]
        signature = bytes(range(256))  # real codes end with a 256-byte signature
        payload = str(int.from_bytes(gzip.compress(b"\xff".join(fields) + b"\xff" * 10 + signature), "big"))
        result = qr.verify(payload, {"name": "VIDHI SHARMA", "dateOfBirth": "2001-06-14", "gender": "FEMALE"},
                           "aadhaar")
        self.assertEqual(len(result["passed"]), 3, result)
        mismatch = qr.verify(payload, {"name": "SOMEONE ELSE"}, "aadhaar")
        self.assertTrue(mismatch["problems"])

    def test_flags_unofficial_verification_links(self):
        official = qr.verify("https://results.cbse.nic.in/verify?roll=25147975", {"rollNumber": "25147975"},
                             "marksheet10")
        unofficial = qr.verify("https://cbse-results.example.com/verify", {}, "marksheet10")
        self.assertTrue(official["passed"] and not official["problems"])
        self.assertTrue(unofficial["problems"])

    def test_reads_a_generated_qr_code(self):
        encoder = cv2.QRCodeEncoder.create()
        code = encoder.encode("ROLL 25147975 VAIBHAV KUMAR")
        image = cv2.cvtColor(cv2.resize(code, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST),
                             cv2.COLOR_GRAY2BGR)
        image = cv2.copyMakeBorder(image, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        self.assertEqual(qr.decode([image]), "ROLL 25147975 VAIBHAV KUMAR")


class TamperTests(unittest.TestCase):
    def test_pdf_metadata_from_editing_tool_is_reported(self):
        findings = tamper.pdf_metadata_findings({"Producer": "Adobe Photoshop 25.0",
                                                 "CreationDate": "D:20200101", "ModDate": "D:20240101"})
        self.assertEqual(len(findings), 2)

    def test_flags_a_value_pasted_on_a_different_background(self):
        page = np.full((700, 600, 3), 225, dtype=np.uint8)
        lines = []
        for row in range(8):
            y = 60 + row * 70
            words = []
            for column, x in enumerate((100, 250, 400)):
                text = f"0{row}{column}"
                if row == 4 and column == 2:
                    # A white patch with a heavier, larger number pasted over the original.
                    cv2.rectangle(page, (x - 6, y - 8), (x + 76, y + 36), (255, 255, 255), -1)
                    cv2.putText(page, text, (x, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 3)
                    words.append(Word(text, 0.99, x, y - 2, x + 70, y + 34))
                else:
                    cv2.putText(page, text, (x, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (70, 70, 70), 2)
                    words.append(Word(text, 0.99, x, y, x + 52, y + 26))
            lines.append(Line([Word("SUBJECT", 0.99, 10, y, 80, y + 26)] + words, 0))
        flagged = tamper.find_inconsistent_values(page, lines)
        self.assertEqual([f["text"] for f in flagged], ["042"])


if __name__ == "__main__":
    unittest.main()
