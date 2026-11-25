import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docverify.app import create_app
from tests.helpers import (GENUINE_MARKSHEET, TAMPERED_MARKSHEET, fake_read_document, make_pdf,
                           make_png)


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.reference_root = Path(self.temp.name) / "references"
        self.app = create_app(self.reference_root, database_url=f"sqlite:///{self.temp.name}/test.db")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.admin = self.register("Admin", "admin@example.com")
        self.user = self.register("User", "user@example.com")

    def tearDown(self):
        self.app.config["DB"].kw["bind"].dispose()
        self.temp.cleanup()

    def register(self, name, email, password="password123"):
        response = self.client.post("/auth/register", json={"name": name, "email": email, "password": password})
        self.assertEqual(response.status_code, 201, response.json)
        return {"Authorization": f"Bearer {response.json['token']}", "role": response.json["user"]["role"]}

    @staticmethod
    def headers(account):
        return {"Authorization": account["Authorization"]}

    def verify(self, account, text, document_type="marksheet10", filename="marksheet.pdf", data=None):
        with patch("docverify.engine.read_document", fake_read_document(text)):
            return self.client.post(
                "/documents/verify",
                data={"documentType": document_type, "file": (io.BytesIO(data or make_pdf()), filename)},
                content_type="multipart/form-data",
                headers=self.headers(account),
            )

    def result(self, account, response):
        return self.client.get(f"/documents/result/{response.json['id']}", headers=self.headers(account)).json

    def layer(self, result, key):
        return next(layer for layer in result["layers"] if layer["key"] == key)


class AuthTests(ApiTestCase):
    def test_first_account_is_admin_and_later_accounts_are_users(self):
        self.assertEqual(self.admin["role"], "admin")
        self.assertEqual(self.user["role"], "user")

    def test_rejects_duplicate_email(self):
        response = self.client.post("/auth/register", json={
            "name": "Again", "email": "USER@example.com", "password": "password123"})
        self.assertEqual(response.status_code, 409)

    def test_rejects_short_password_and_bad_email(self):
        short = self.client.post("/auth/register", json={"name": "A", "email": "a@b.co", "password": "short"})
        bad_email = self.client.post("/auth/register", json={"name": "A", "email": "nope", "password": "password123"})
        self.assertEqual(short.status_code, 400)
        self.assertEqual(bad_email.status_code, 400)

    def test_login_and_me(self):
        response = self.client.post("/auth/login", json={"email": "user@example.com", "password": "password123"})
        self.assertEqual(response.status_code, 200)
        me = self.client.get("/auth/me", headers={"Authorization": f"Bearer {response.json['token']}"})
        self.assertEqual(me.json["user"]["email"], "user@example.com")

    def test_wrong_password_is_rejected(self):
        response = self.client.post("/auth/login", json={"email": "user@example.com", "password": "wrong-pass"})
        self.assertEqual(response.status_code, 401)

    def test_protected_routes_need_a_valid_token(self):
        self.assertEqual(self.client.get("/documents/history").status_code, 401)
        bad = self.client.get("/documents/history", headers={"Authorization": "Bearer forged"})
        self.assertEqual(bad.status_code, 401)


class PublicRouteTests(ApiTestCase):
    def test_health(self):
        self.assertEqual(self.client.get("/health").json, {"status": "ok"})

    def test_allows_frontend_on_any_local_port_only(self):
        local = self.client.get("/health", headers={"Origin": "http://localhost:5174"})
        remote = self.client.get("/health", headers={"Origin": "http://evil.example.com"})
        self.assertEqual(local.headers.get("Access-Control-Allow-Origin"), "http://localhost:5174")
        self.assertIsNone(remote.headers.get("Access-Control-Allow-Origin"))

    def test_lists_document_types_with_required_fields(self):
        types = {t["id"]: t for t in self.client.get("/documents/types").json}
        self.assertEqual(set(types), {"marksheet10", "marksheet12", "jeeResult", "tc", "domicile", "aadhaar"})
        self.assertIn("Roll number", types["marksheet10"]["requiredFields"])
        self.assertEqual(types["jeeResult"]["formats"], [".pdf"])


class ReferenceTests(ApiTestCase):
    def upload_reference(self, account, document_type="marksheet10", data=None, filename="source.pdf"):
        return self.client.post(
            "/documents/references",
            data={"documentType": document_type, "file": (io.BytesIO(data or make_pdf()), filename)},
            content_type="multipart/form-data",
            headers=self.headers(account),
        )

    def test_admin_uploads_lists_and_deletes_reference(self):
        response = self.upload_reference(self.admin)
        self.assertEqual(response.status_code, 201)
        listed = self.client.get("/documents/references", headers=self.headers(self.user)).json
        self.assertEqual(len(listed["marksheet10"]), 1)
        self.assertEqual(listed["marksheet12"], [])

        filename = response.json["filename"]
        deleted = self.client.delete(f"/documents/references/marksheet10/{filename}", headers=self.headers(self.admin))
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse((self.reference_root / "marksheet10" / filename).exists())

    def test_regular_user_cannot_manage_references(self):
        self.assertEqual(self.upload_reference(self.user).status_code, 403)

    def test_rejects_image_reference_for_jee(self):
        response = self.upload_reference(self.admin, "jeeResult", make_png(), "result.png")
        self.assertEqual(response.status_code, 400)

    def test_rejects_unreadable_pdf(self):
        response = self.upload_reference(self.admin, data=b"%PDF-1.4 broken")
        self.assertEqual(response.status_code, 400)

    def test_rejects_path_traversal_on_delete(self):
        response = self.client.delete("/documents/references/marksheet10/..%2Fsecret.pdf",
                                      headers=self.headers(self.admin))
        self.assertIn(response.status_code, (400, 404))


class VerificationTests(ApiTestCase):
    def test_requires_sign_in(self):
        response = self.client.post("/documents/verify", data={"documentType": "marksheet10"})
        self.assertEqual(response.status_code, 401)

    def test_rejects_unknown_type_and_invalid_file(self):
        unknown = self.verify(self.user, GENUINE_MARKSHEET, document_type="passport")
        invalid = self.verify(self.user, GENUINE_MARKSHEET, data=b"not a pdf")
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(invalid.status_code, 400)

    def test_genuine_marksheet_is_verified_with_extracted_fields(self):
        result = self.result(self.user, self.verify(self.user, GENUINE_MARKSHEET))
        self.assertEqual(result["verdict"], "verified", result["layers"])
        fields = {f["key"]: f["value"] for f in result["fields"]}
        self.assertEqual(fields["name"], "VAIBHAV KUMAR")
        self.assertEqual(fields["rollNumber"], "25147975")
        self.assertEqual(fields["dateOfBirth"], "2004-05-08")
        self.assertEqual(len(result["subjects"]), 5)
        self.assertEqual(self.layer(result, "consistency")["status"], "pass")
        self.assertEqual(self.layer(result, "classification")["detectedType"], "marksheet10")

    def test_inconsistent_marks_make_the_document_suspicious(self):
        result = self.result(self.user, self.verify(self.user, TAMPERED_MARKSHEET))
        self.assertEqual(result["verdict"], "suspicious")
        consistency = self.layer(result, "consistency")
        self.assertEqual(consistency["status"], "fail")
        self.assertTrue(any("Mathematics Standard" in d and "90" in d for d in consistency["details"]))
        self.assertGreaterEqual(result["riskScore"], 55)

    def test_missing_required_fields_need_review(self):
        text = "CENTRAL BOARD OF SECONDARY EDUCATION\nMARKS STATEMENT\nsome text without the usual fields here"
        result = self.result(self.user, self.verify(self.user, text))
        self.assertEqual(self.layer(result, "structure")["status"], "fail")
        self.assertIn(result["verdict"], ("review", "suspicious"))

    def test_unreadable_text_needs_review(self):
        result = self.result(self.user, self.verify(self.user, "x"))
        self.assertEqual(result["verdict"], "review")
        self.assertEqual(self.layer(result, "ocr")["status"], "fail")

    def test_wrong_document_type_is_flagged(self):
        result = self.result(self.user, self.verify(self.user, GENUINE_MARKSHEET, document_type="domicile"))
        self.assertEqual(self.layer(result, "classification")["status"], "fail")

    def test_matching_reference_passes(self):
        reference = self.reference_root / "marksheet10" / "ref-genuine.pdf"
        reference.parent.mkdir(parents=True)
        reference.write_bytes(make_pdf())
        reference.with_name(reference.name + ".txt").write_text(GENUINE_MARKSHEET, encoding="utf8")
        result = self.result(self.user, self.verify(self.user, GENUINE_MARKSHEET))
        self.assertEqual(self.layer(result, "reference")["status"], "pass")

    def test_reference_for_same_record_with_different_marks_is_suspicious(self):
        reference = self.reference_root / "marksheet10" / "ref-genuine.pdf"
        reference.parent.mkdir(parents=True)
        reference.write_bytes(make_pdf())
        reference.with_name(reference.name + ".txt").write_text(GENUINE_MARKSHEET, encoding="utf8")
        altered = GENUINE_MARKSHEET.replace("077 020 097 NINETY SEVEN", "087 010 097 NINETY SEVEN") \
            .replace("Mother's Name ASHA RANI", "Mother's Name SUNITA DEVI KUMARI") \
            .replace("School 81270 SAI MILLENIUM SCHOOL", "School 99999 OTHER PUBLIC SCHOOL ROAD")
        result = self.result(self.user, self.verify(self.user, altered))
        reference_layer = self.layer(result, "reference")
        self.assertEqual(reference_layer["status"], "fail", reference_layer)
        self.assertEqual(result["verdict"], "suspicious")

    def test_authorized_record_match_and_mismatch(self):
        created = self.client.post("/records", headers=self.headers(self.admin), json={
            "documentType": "marksheet10", "identifier": "25147975", "name": "Vaibhav Kumar",
            "fields": {"dateOfBirth": "2004-05-08", "subjects": {"MATHEMATICS STANDARD": 100}},
            "source": "CBSE results portal"})
        self.assertEqual(created.status_code, 201)
        genuine = self.result(self.user, self.verify(self.user, GENUINE_MARKSHEET))
        self.assertEqual(self.layer(genuine, "records")["status"], "pass")

        self.client.delete(f"/records/{created.json['id']}", headers=self.headers(self.admin))
        self.client.post("/records", headers=self.headers(self.admin), json={
            "documentType": "marksheet10", "identifier": "25147975", "name": "Vaibhav Kumar",
            "fields": {"subjects": {"MATHEMATICS STANDARD": 72}}})
        mismatch = self.result(self.user, self.verify(self.user, GENUINE_MARKSHEET))
        self.assertEqual(self.layer(mismatch, "records")["status"], "fail")
        self.assertEqual(mismatch["verdict"], "suspicious")

    def test_records_csv_import(self):
        csv_text = ("documentType,identifier,name,source,dateOfBirth,subject:MATHEMATICS STANDARD\n"
                    "marksheet10,25147975,Vaibhav Kumar,Board,2004-05-08,100\n"
                    "unknown,1,Bad,,,\n")
        response = self.client.post("/records/import", headers=self.headers(self.admin),
                                    data={"file": (io.BytesIO(csv_text.encode()), "records.csv")},
                                    content_type="multipart/form-data")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["imported"], 1)
        self.assertEqual(len(response.json["errors"]), 1)
        records = self.client.get("/records", headers=self.headers(self.admin)).json
        self.assertEqual(records[0]["fields"]["subjects"], {"MATHEMATICS STANDARD": "100"})

    def test_users_only_see_their_own_history_and_results(self):
        mine = self.verify(self.user, GENUINE_MARKSHEET)
        other = self.register("Other", "other@example.com")
        self.assertEqual(self.client.get(f"/documents/result/{mine.json['id']}",
                                         headers=self.headers(other)).status_code, 404)
        history = self.client.get("/documents/history", headers=self.headers(self.user)).json
        self.assertEqual([h["id"] for h in history], [mine.json["id"]])
        self.assertEqual(self.client.get("/documents/history", headers=self.headers(other)).json, [])
        admin_all = self.client.get("/documents/history?scope=all", headers=self.headers(self.admin)).json
        self.assertEqual(len(admin_all), 1)

    def test_delete_result(self):
        response = self.verify(self.user, GENUINE_MARKSHEET)
        deleted = self.client.delete(f"/documents/result/{response.json['id']}", headers=self.headers(self.user))
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get(f"/documents/result/{response.json['id']}",
                                         headers=self.headers(self.user)).status_code, 404)

    def test_results_persist_across_app_restarts(self):
        response = self.verify(self.user, GENUINE_MARKSHEET)
        restarted = create_app(self.reference_root, database_url=f"sqlite:///{self.temp.name}/test.db")
        result = restarted.test_client().get(f"/documents/result/{response.json['id']}",
                                             headers=self.headers(self.user))
        self.assertEqual(result.status_code, 200)
        restarted.config["DB"].kw["bind"].dispose()


if __name__ == "__main__":
    unittest.main()
