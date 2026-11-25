# DocVerify AI

Intelligent document verification and fraud detection. DocVerify AI reads an uploaded
document, extracts its information, checks that it is complete and consistent, looks for
signs of editing, verifies QR codes and authorized records, and explains its verdict:
**Verified**, **Requires Review** or **Suspicious**, with a 0–100 risk score.

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

Supported types: 10th and 12th marksheets, JEE result, transfer certificate, domicile
certificate and Aadhaar card.

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

The first verification after starting the backend takes 1–2 minutes while EasyOCR loads
(and, the very first time, downloads) its model. After that a document takes about 10
seconds on CPU.

## Configuration

Copy `.env.example` values into your environment as needed:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///backend/instance/docverify.db` | Database; e.g. `postgresql+psycopg://user:pass@localhost/docverify` (install `psycopg[binary]`) |
| `SECRET_KEY` | random key saved in `backend/instance/secret_key` | Signs sign-in tokens |
| `REFERENCE_ROOT` | `backend/references` | Where genuine reference documents are stored |
| `VITE_API_BASE_URL` | `http://127.0.0.1:5000` | Backend URL used by the frontend |

`backend/instance/` and stored references are excluded from Git.

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
