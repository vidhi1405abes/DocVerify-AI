import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

import manage
from docverify.app import create_app


class ManageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(self.temp.name, database_url=f"sqlite:///{self.temp.name}/test.db")
        self.client = self.app.test_client()
        self.client.post("/auth/register", json={"name": "Owner", "email": "owner@example.com",
                                                 "password": "forgotten-pass"})
        self.client.post("/auth/register", json={"name": "Second", "email": "second@example.com",
                                                 "password": "password123"})
        self.sessions = self.app.config["DB"]

    def tearDown(self):
        self.sessions.kw["bind"].dispose()
        self.temp.cleanup()

    def login(self, email, password):
        return self.client.post("/auth/login", json={"email": email, "password": password}).status_code

    def test_reset_password_lets_the_user_sign_in_again(self):
        with redirect_stdout(StringIO()):
            self.assertEqual(manage.reset_password(self.sessions, "OWNER@example.com", "brand-new-pass"), 0)
        self.assertEqual(self.login("owner@example.com", "brand-new-pass"), 200)
        self.assertEqual(self.login("owner@example.com", "forgotten-pass"), 401)

    def test_reset_rejects_short_password_and_unknown_email(self):
        with redirect_stderr(StringIO()):
            self.assertEqual(manage.reset_password(self.sessions, "owner@example.com", "short"), 1)
            self.assertEqual(manage.reset_password(self.sessions, "nobody@example.com", "long-enough"), 1)
        self.assertEqual(self.login("owner@example.com", "forgotten-pass"), 200)

    def test_make_admin_and_list_users(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(manage.make_admin(self.sessions, "second@example.com"), 0)
            manage.list_users(self.sessions)
        self.assertIn("second@example.com", output.getvalue())
        self.assertEqual(output.getvalue().count("admin"), 3)


if __name__ == "__main__":
    unittest.main()
