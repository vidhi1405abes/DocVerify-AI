"""Logical and mathematical consistency checks on extracted fields."""

from datetime import date

from .textutils import verhoeff_valid

PASS_MARK = 33
CONFIDENT = 0.75


class Findings:
    def __init__(self):
        self.passed, self.problems = [], []

    def ok(self, message):
        self.passed.append(message)

    def problem(self, message, confident=True):
        self.problems.append({"message": message, "severity": "fail" if confident else "warn"})


def _date(value):
    try:
        return date.fromisoformat(value) if value and len(value) == 10 else None
    except ValueError:
        return None


def _check_subject_rows(rows, findings):
    consistent_rows = 0
    for row in rows:
        subject = row["subject"].title()
        tokens = row["tokens"]
        theory, practical, total = row["theory"], row["practical"], row["total"]
        from_words = row["totalFromWords"]
        row_ok = True

        if total is not None and total > 100:
            findings.problem(f"{subject}: total {total} is more than the maximum of 100.",
                             tokens.get("total", 0) >= CONFIDENT)
            row_ok = False

        if theory is not None and total is not None:
            components = theory + (practical or 0)
            if components != total:
                confident = min(tokens.values()) >= CONFIDENT
                if from_words is not None and from_words == components:
                    message = (f"{subject}: printed total {total} does not match the marks "
                               f"({theory} + {practical or 0} = {components}) or the total in words "
                               f"({row['totalInWords'].title()}).")
                else:
                    message = (f"{subject}: marks {theory} + {practical or 0} = {components}, "
                               f"but the printed total is {total}.")
                findings.problem(message, confident)
                row_ok = False

        if from_words is not None and total is not None and from_words != total:
            if not (theory is not None and theory + (practical or 0) == from_words):
                findings.problem(
                    f"{subject}: total in figures ({total}) and in words "
                    f"({row['totalInWords'].title()} = {from_words}) disagree.",
                    tokens.get("total", 0) >= CONFIDENT,
                )
                row_ok = False

        consistent_rows += row_ok
    if consistent_rows:
        findings.ok(f"{consistent_rows} of {len(rows)} subject rows add up correctly.")


def _check_result(fields, findings):
    rows = fields.get("subjects") or []
    result = (fields.get("result") or "").upper()
    failing = [r for r in rows if r["total"] is not None and r["total"] < PASS_MARK]
    if result.startswith("PASS") and failing:
        names = ", ".join(r["subject"].title() for r in failing)
        findings.problem(f"Result says PASS but {names} is below the pass mark of {PASS_MARK}.",
                         min(r["confidence"] for r in failing) >= CONFIDENT)
    elif result.startswith("PASS") and rows:
        findings.ok("Result PASS agrees with the marks in every subject.")
    elif result.startswith("FAIL") and rows and not failing:
        findings.problem(f"Result says FAIL but every subject is at or above the pass mark of {PASS_MARK}.",
                         min(r["confidence"] for r in rows) >= CONFIDENT)

    grand_total = fields.get("grandTotal")
    if grand_total and rows:
        totals = [r["total"] for r in rows if r["total"] is not None]
        if int(grand_total) not in (sum(totals), sum(totals[:5])):
            findings.problem(f"Grand total {grand_total} does not equal the sum of subject totals ({sum(totals)}).")
        else:
            findings.ok(f"Grand total {grand_total} equals the sum of subject totals.")


def _check_dates(document_type, fields, findings):
    today = date.today()
    birth = _date(fields.get("dateOfBirth"))
    if birth:
        if birth > today:
            findings.problem("Date of birth is in the future.")
        elif not 1900 < birth.year:
            findings.problem(f"Date of birth year {birth.year} is not plausible.")
        else:
            findings.ok("Date of birth is a valid calendar date.")

    words = _date(fields.get("dateOfBirthInWords"))
    if birth and words:
        if birth == words:
            findings.ok("Date of birth in figures matches the date in words.")
        else:
            findings.problem(f"Date of birth in figures ({birth.isoformat()}) differs from the date in "
                             f"words ({words.isoformat()}).")

    year = fields.get("examYear")
    if birth and year:
        age = year - birth.year
        expected = {"marksheet10": (13, 22), "marksheet12": (15, 25), "jeeResult": (15, 30)}.get(document_type)
        if expected and not expected[0] <= age <= expected[1]:
            findings.problem(f"Candidate would be {age} at the {year} examination, which is unusual for "
                             "this document.", confident=False)
        elif expected:
            findings.ok(f"Age at the {year} examination ({age}) is plausible.")

    issued = _date(fields.get("issueDate"))
    if issued:
        if issued > today:
            findings.problem("Date of issue is in the future.")
        elif year and issued.year < year:
            findings.problem(f"Issued in {issued.year}, before the {year} examination took place.")
        elif birth and issued <= birth:
            findings.problem("Date of issue is before the date of birth.")
        else:
            findings.ok("Date of issue is consistent with the other dates.")

    admitted, left = _date(fields.get("admissionDate")), _date(fields.get("leavingDate"))
    if admitted and left:
        if left < admitted:
            findings.problem("Date of leaving is earlier than the date of admission.")
        else:
            findings.ok("Admission and leaving dates are in order.")
    if birth and admitted and admitted <= birth:
        findings.problem("Date of admission is before the date of birth.")


def _check_scores(fields, findings):
    for key, label, upper in (("totalPercentile", "Percentile", 100), ("percentage", "Percentage", 100),
                              ("cgpa", "CGPA", 10)):
        if key in fields:
            value = float(fields[key])
            if not 0 <= value <= upper:
                findings.problem(f"{label} {value} is outside the valid range 0-{upper}.")
            else:
                findings.ok(f"{label} {value} is within the valid range.")


def _check_aadhaar(fields, findings):
    number = fields.get("aadhaarNumber", "")
    if number.isdigit() and len(number) == 12:
        if number[0] in "01":
            findings.problem("Aadhaar numbers never start with 0 or 1.")
        elif verhoeff_valid(number):
            findings.ok("Aadhaar number passes the Verhoeff checksum.")
        else:
            findings.problem("Aadhaar number fails the Verhoeff checksum, so it is not a valid number.")


def check(document_type, fields):
    findings = Findings()
    if fields.get("subjects"):
        _check_subject_rows(fields["subjects"], findings)
    _check_result(fields, findings)
    _check_dates(document_type, fields, findings)
    _check_scores(fields, findings)
    if document_type == "aadhaar":
        _check_aadhaar(fields, findings)
    return findings
