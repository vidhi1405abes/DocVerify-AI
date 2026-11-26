# DocVerify AI

Intelligent document verification and fraud detection. DocVerify AI reads an uploaded
document, extracts its information, checks that it is complete and consistent, looks for
signs of editing, verifies QR codes and authorized records, and explains its verdict:
**Verified**, **Requires Review**, **Suspicious** or **Rejected**, with a 0–100 risk score.

Results support a human verifier; they are not proof of official authenticity.

**Privacy:** real or sample documents (marksheets, ID cards) are never committed. Keep test
documents in `backend/IMG/`, which Git ignores.

The full specification is in [requirements.pdf](requirements.pdf).

## Verification pipeline

| Layer | What it checks |
|---|---|
| Preprocessing | Upscales small scans, straightens tilt, removes noise, boosts contrast (OpenCV) |
| OCR | Reads the text with EasyOCR and rebuilds reading-order lines |
| Classification | Recognises the document type (scikit-learn TF-IDF + logistic regression) |
| Extraction & structure | Pulls out names, IDs, dates and marks; checks mandatory fields |
| Data consistency | Marks add up, totals match the total in words, dates are valid and in order, Aadhaar Verhoeff checksum |
| Tampering | Printed values that differ in size, ink or background from the rest of the table; editing software in file metadata |
| QR / document ID | Decodes QR codes (including Aadhaar secure QR) and compares them with the printed details |
| Authorized records | Compares the document field by field with records from an authorized source |
| Reference documents | Compares with genuine references of the same record |
| Previous verifications | Flags a roll or certificate number verified before with a different name or marks |

**Verdicts:** *Rejected* (risk 90+) when a mandatory field is missing, the file is unreadable or it is not a
supported document; *Suspicious* (risk 70+) for the wrong document type, inconsistent marks or a record
mismatch; *Requires Review* for risk 25–54; *Verified* below 25. Times are shown in IST.

Supported types: 10th and 12th marksheets, JEE result, transfer certificate, domicile
certificate (or application) and Aadhaar card. Files: PDF, JPG, PNG and WebP.

## Built for Indian documents

- **Hindi + English.** Every text region is read by the English model; regions it cannot read
  confidently (usually Hindi) are re-read by the Devanagari model, and the better reading is kept.
  Hindi labels (नाम, पिता का नाम, जन्म तिथि, अनुक्रमांक, प्रमाण पत्र संख्या…), Hindi gender words and
  Devanagari digits (२०२०) are understood. Bilingual values keep the English spelling when printed.
- **Digital PDFs (DigiLocker, e-Aadhaar)** are read from their embedded text: exact, with no OCR.
  Password-protected PDFs are supported (e-Aadhaar: first 4 letters of the name in capitals + year
  of birth), and a digital signature is reported when present.
- **Forwarded photos.** Small or blurry images are enlarged, cleaned up and read twice; when text
  is still unreadable the result says what to ask the sender for (share on WhatsApp as a
  *Document*, or send the DigiLocker PDF).

## Tech stack

React 18 + Vite + Tailwind CSS · Flask (Python) · SQLAlchemy with SQLite (PostgreSQL via
`DATABASE_URL`) · EasyOCR + PyTorch · OpenCV · scikit-learn · pypdfium2.

## Run locally

Requirements: Node.js 18+ and Python 3.10+.

Backend (first terminal):

```powershell
python -m pip install -r backend\requirements.txt
python backend\run.py
```

Frontend (second terminal):

```powershell
npm install
npm run dev
```

Open http://localhost:5173 and create an account. **The first account becomes the
administrator**, who manages reference documents and authorized records; later accounts
can verify documents and see their own history.

The first verification after starting the backend takes 1–2 minutes while EasyOCR loads its
models. The very first time it also downloads them (English ~100 MB, Hindi ~215 MB). After
that a document takes about 10–40 seconds on CPU, depending on how much Hindi text it has.

## Configuration

Copy `.env.example` values into your environment as needed:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///backend/instance/docverify.db` | Database; e.g. `postgresql+psycopg://user:pass@localhost/docverify` (install `psycopg[binary]`) |
| `SECRET_KEY` | random key saved in `backend/instance/secret_key` | Signs sign-in tokens |
| `REFERENCE_ROOT` | `backend/references` | Where genuine reference documents are stored |
| `VITE_API_BASE_URL` | `http://127.0.0.1:5000` | Backend URL used by the frontend |

`backend/instance/` and stored references are excluded from Git.

## Forgot your password?

The app has no email service, so passwords are reset on the computer that runs the backend:

```powershell
python backend\manage.py list-users
python backend\manage.py reset-password you@example.com
```

You are asked for the new password twice (the typing is hidden). `make-admin <email>` gives
another account administrator rights.

## Authorized records

Admins add records on the **Authorized records** page, one at a time or by CSV:

```csv
documentType,identifier,name,source,dateOfBirth,result,subject:MATHEMATICS,subject:SCIENCE
marksheet10,25147975,Vaibhav Kumar,CBSE results portal,2004-05-08,PASS,100,95
```

A verified document is looked up by its roll, application or certificate number and every
value in the record is compared with it.

## Checks

```powershell
npm run lint
npm run build
python -m unittest discover -s backend -t backend
```

## Project layout

```
backend/
  docverify/      app (routes), auth, models, engine (layers + risk score),
                  ocr, extract, classify, consistency, tamper, qr, doc_types
  tests/          API and verification-layer tests
  IMG/            your local sample documents (ignored by Git, never uploaded)
src/
  pages/          Home, Auth, Verify, Results, History, Admin (references, records)
  components/     layout, UI and document components
  services/api/   API client
```
