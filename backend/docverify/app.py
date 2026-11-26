import csv
import io
import json
import os
import threading
import uuid
from pathlib import Path

from flask import Flask, current_app, g, jsonify, request
from flask_cors import CORS
from sqlalchemy import select
from werkzeug.utils import secure_filename

from . import engine, ocr
from .auth import admin_required, bp as auth_bp, json_error, login_required
from .config import (ALLOWED_ORIGINS, BACKEND_DIR, MAX_UPLOAD_BYTES, SUPPORTED_EXTENSIONS,
                     default_database_url, secret_key)
from .doc_types import DOCUMENT_TYPES, public_types
from .models import AuthorizedRecord, Verification, make_session_factory, utc_iso

HISTORY_LIMIT = 200


def _read_upload(document_type):
    """Validate the uploaded file and type. Returns (bytes, extension, filename) or an error response."""
    uploaded = request.files.get("file")
    if document_type not in DOCUMENT_TYPES:
        return None, json_error("Select a supported document type.", 400)
    if uploaded is None or not uploaded.filename:
        return None, json_error("Choose a document to upload.", 400)

    extension = Path(uploaded.filename).suffix.lower()
    allowed = DOCUMENT_TYPES[document_type]["formats"]
    if extension not in SUPPORTED_EXTENSIONS:
        return None, json_error("Upload a PDF, JPG, JPEG, or PNG document.", 400)
    if extension not in allowed:
        return None, json_error(f"{DOCUMENT_TYPES[document_type]['name']} documents must be PDF files.", 400)

    file_bytes = uploaded.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        return None, json_error("File exceeds the 15 MB upload limit.", 413)
    if not ocr.is_readable(file_bytes, extension):
        kind = "PDF" if extension == ".pdf" else "image"
        return None, json_error(f"The selected file is not a readable {kind}.", 400)
    return (file_bytes, extension, secure_filename(uploaded.filename) or f"document{extension}"), None


def _records_for(document_type):
    with current_app.config["DB"]() as session:
        return session.scalars(
            select(AuthorizedRecord).where(AuthorizedRecord.document_type == document_type)
        ).all()


def _verified_results(document_type, limit=1000):
    """Earlier results of this type that passed, to catch reused IDs with changed details."""
    with current_app.config["DB"]() as session:
        rows = session.scalars(
            select(Verification)
            .where(Verification.document_type == document_type, Verification.verdict == "verified")
            .order_by(Verification.created_at.desc())
            .limit(limit)
        ).all()
    return [json.loads(row.result_json) for row in rows]


def create_app(reference_root=None, database_url=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.config["SECRET_KEY"] = secret_key()
    app.config["REFERENCE_ROOT"] = Path(
        reference_root or os.environ.get("REFERENCE_ROOT") or BACKEND_DIR / "references"
    )
    app.config["DB"] = make_session_factory(database_url or default_database_url())
    CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})
    app.register_blueprint(auth_bp)

    @app.errorhandler(413)
    def file_too_large(_error):
        return json_error("File exceeds the 15 MB upload limit.", 413)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/documents/types")
    def document_types():
        return jsonify(public_types())

    # ------------------------------------------------------------ references

    @app.get("/documents/references")
    @login_required
    def list_references():
        root = app.config["REFERENCE_ROOT"]
        return jsonify({
            type_id: [{"filename": p.name, "displayName": p.name.split("-", 1)[-1]}
                      for p in engine.list_references(root, type_id)]
            for type_id in DOCUMENT_TYPES
        })

    @app.post("/documents/references")
    @admin_required
    def upload_reference():
        document_type = request.form.get("documentType", "")
        upload, error = _read_upload(document_type)
        if error:
            return error
        file_bytes, _, display_name = upload
        directory = app.config["REFERENCE_ROOT"] / document_type
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid.uuid4().hex}-{display_name}"
        path.write_bytes(file_bytes)
        if not app.config.get("TESTING"):
            # Read the reference now so later verifications and the classifier can use it.
            threading.Thread(target=engine.reference_text, args=(path,), daemon=True).start()
        return jsonify({"documentType": document_type, "filename": path.name,
                        "displayName": display_name}), 201

    @app.delete("/documents/references/<document_type>/<filename>")
    @admin_required
    def delete_reference(document_type, filename):
        if document_type not in DOCUMENT_TYPES:
            return json_error("Unknown document type.", 404)
        if secure_filename(filename) != filename or Path(filename).name != filename:
            return json_error("Invalid reference document name.", 400)
        path = app.config["REFERENCE_ROOT"] / document_type / filename
        if not path.is_file():
            return json_error("Reference document not found.", 404)
        path.unlink()
        path.with_name(path.name + ".txt").unlink(missing_ok=True)
        return jsonify({"deleted": True})

    # ------------------------------------------------------------ verification

    @app.post("/documents/verify")
    @login_required
    def verify_document():
        document_type = request.form.get("documentType", "")
        upload, error = _read_upload(document_type)
        if error:
            return error
        file_bytes, extension, filename = upload
        result = engine.run(document_type, file_bytes, extension, filename,
                            app.config["REFERENCE_ROOT"], _records_for(document_type),
                            _verified_results(document_type))

        with app.config["DB"]() as session:
            verification = Verification(
                user_id=g.user.id, document_type=document_type, filename=filename,
                verdict=result["verdict"], risk_score=result["riskScore"], result_json="{}",
            )
            session.add(verification)
            session.flush()
            result["id"] = verification.id
            result["createdAt"] = utc_iso(verification.created_at)
            verification.result_json = json.dumps(result)
            session.commit()
        return jsonify({"id": result["id"], "verdict": result["verdict"]}), 201

    def _own_verification(session, result_id):
        verification = session.get(Verification, result_id)
        if verification is None or (verification.user_id != g.user.id and g.user.role != "admin"):
            return None
        return verification

    @app.get("/documents/result/<result_id>")
    @login_required
    def get_result(result_id):
        with app.config["DB"]() as session:
            verification = _own_verification(session, result_id)
            if verification is None:
                return json_error("Result not found.", 404)
            return app.response_class(verification.result_json, mimetype="application/json")

    @app.delete("/documents/result/<result_id>")
    @login_required
    def delete_result(result_id):
        with app.config["DB"]() as session:
            verification = _own_verification(session, result_id)
            if verification is None:
                return json_error("Result not found.", 404)
            session.delete(verification)
            session.commit()
        return jsonify({"deleted": True})

    @app.get("/documents/history")
    @login_required
    def history():
        with app.config["DB"]() as session:
            query = select(Verification).order_by(Verification.created_at.desc()).limit(HISTORY_LIMIT)
            if g.user.role != "admin" or request.args.get("scope") != "all":
                query = query.where(Verification.user_id == g.user.id)
            return jsonify([v.summary() for v in session.scalars(query)])

    # ------------------------------------------------------------ authorized records

    def _record_from(payload):
        document_type = str(payload.get("documentType", ""))
        identifier = str(payload.get("identifier", "")).strip()
        if document_type not in DOCUMENT_TYPES:
            raise ValueError("Select a supported document type.")
        if not identifier:
            raise ValueError("Identifier (roll number, certificate or application number) is required.")
        fields = payload.get("fields") or {}
        if not isinstance(fields, dict):
            raise ValueError("Fields must be an object of field name to value.")
        return AuthorizedRecord(
            document_type=document_type, identifier=identifier,
            name=str(payload.get("name", "")).strip().upper(),
            fields_json=json.dumps(fields), source=str(payload.get("source", "")).strip(),
        )

    @app.get("/records")
    @admin_required
    def list_records():
        with app.config["DB"]() as session:
            records = session.scalars(select(AuthorizedRecord).order_by(AuthorizedRecord.created_at.desc()))
            return jsonify([r.to_dict() for r in records])

    @app.post("/records")
    @admin_required
    def create_record():
        try:
            record = _record_from(request.get_json(silent=True) or {})
        except ValueError as error:
            return json_error(str(error), 400)
        with app.config["DB"]() as session:
            session.add(record)
            session.commit()
            return jsonify(record.to_dict()), 201

    @app.post("/records/import")
    @admin_required
    def import_records():
        """CSV columns: documentType, identifier, name, source, then any extra field columns.

        A column named subject:<NAME> holds that subject's total, e.g. subject:MATHEMATICS.
        """
        uploaded = request.files.get("file")
        if uploaded is None:
            return json_error("Choose a CSV file to import.", 400)
        try:
            rows = list(csv.DictReader(io.StringIO(uploaded.read().decode("utf-8-sig"))))
        except (UnicodeDecodeError, csv.Error):
            return json_error("The file is not a readable CSV.", 400)
        created, errors = [], []
        for number, row in enumerate(rows, start=2):
            fields, subjects = {}, {}
            for column, value in row.items():
                if not column or value in (None, "") or column in ("documentType", "identifier", "name", "source"):
                    continue
                if column.lower().startswith("subject:"):
                    subjects[column.split(":", 1)[1].strip().upper()] = value
                else:
                    fields[column] = value
            if subjects:
                fields["subjects"] = subjects
            try:
                created.append(_record_from({**row, "fields": fields}))
            except ValueError as error:
                errors.append(f"Row {number}: {error}")
        with app.config["DB"]() as session:
            session.add_all(created)
            session.commit()
        return jsonify({"imported": len(created), "errors": errors}), 201 if created else 400

    @app.delete("/records/<int:record_id>")
    @admin_required
    def delete_record(record_id):
        with app.config["DB"]() as session:
            record = session.get(AuthorizedRecord, record_id)
            if record is None:
                return json_error("Record not found.", 404)
            session.delete(record)
            session.commit()
        return jsonify({"deleted": True})

    return app
