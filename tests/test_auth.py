"""Login, route protection and per-user data tests.

The database tests always run on a temporary SQLite file. They also run on
PostgreSQL when TEST_DATABASE_URL is set. They delete only the users they create.
"""

import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import delete

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
os.environ.setdefault("SECRET_KEY", "test-only-secret")

from data_layer import database
from data_layer.user_data import User
from interface_layer.web.app import app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
PASSWORD = "correct-horse-battery"

PROFILE = {
    "height_cm": 165, "weight_kg": 65, "age": 22, "level": "beginner",
    "goals": ["build_muscle"], "equipment": ["dumbbell"], "focus_muscles": [],
    "session_min": 45, "sessions_per_day": 1, "days_per_week": 2,
    "has_pullup_bar": False, "include_stretch": True, "include_hip_mobility": False
}


def token(client, page="/login"):
    """Visit a page so the session has a CSRF token, then return it."""
    client.get(page)
    with client.session_transaction() as test_session:
        return test_session["csrf_token"]


class ProtectionTests(unittest.TestCase):
    """These need no database."""

    def setUp(self):
        self.client = app.test_client()

    def test_pages_redirect_to_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/login"))

    def test_apis_require_login(self):
        for url in ["/api/metadata", "/api/exercises", "/api/workout-sets",
                    "/api/progression?target=Bodyweight%20Squat", "/api/profile"]:
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_login_page_is_public(self):
        self.assertEqual(self.client.get("/login").status_code, 200)
        self.assertEqual(self.client.get("/register").status_code, 200)

    def test_writes_need_the_csrf_token(self):
        self.assertEqual(self.client.post("/api/recommend").status_code, 403)
        self.assertEqual(self.client.put("/api/profile", json=PROFILE).status_code, 403)


class AccountTests(unittest.TestCase):
    """Database tests on SQLite."""

    def make_url(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return "sqlite:///" + os.path.join(folder.name, "test.db")

    def setUp(self):
        previous = os.environ.get("DATABASE_URL")
        self.addCleanup(self.restore_url, previous)
        os.environ["DATABASE_URL"] = self.make_url()
        database.create_tables()
        self.names = []
        self.addCleanup(self.delete_users)

    def restore_url(self, previous):
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous

    def delete_users(self):
        with database.session_scope() as session:
            session.execute(delete(User).where(User.username.in_(self.names)))

    def register(self):
        """Create a new account and return its client and username."""
        name = "test_" + uuid.uuid4().hex[:12]
        self.names.append(name)
        client = app.test_client()
        response = client.post("/register", data={
            "csrf_token": token(client, "/register"), "username": name,
            "email": name + "@example.com", "password": PASSWORD, "confirm_password": PASSWORD
        })
        self.assertEqual(response.status_code, 302)
        return client, name

    def log_in(self, login, password):
        client = app.test_client()
        response = client.post("/login", data={
            "csrf_token": token(client), "login": login, "password": password
        })
        return client, response

    def test_password_is_hashed(self):
        _, name = self.register()
        user = database.find_user_by_login(name)
        self.assertNotIn(PASSWORD, user["password_hash"])

    def test_login_by_username_or_email_and_logout(self):
        _, name = self.register()
        for login in [name, name.upper() + "@Example.com"]:
            client, response = self.log_in(login, PASSWORD)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(client.get("/").status_code, 200)

        client.post("/logout", data={"csrf_token": token(client, "/")})
        self.assertEqual(client.get("/").status_code, 302)
        self.assertEqual(client.get("/api/profile").status_code, 401)

    def test_wrong_credentials(self):
        _, name = self.register()
        for login, password in [(name, "wrong-password"), ("nobody_here", PASSWORD)]:
            client, response = self.log_in(login, password)
            self.assertEqual(response.status_code, 401)
            self.assertIn("Incorrect email/username or password.", response.get_data(as_text=True))
            self.assertEqual(client.get("/api/profile").status_code, 401)

    def test_duplicate_account(self):
        _, name = self.register()
        client = app.test_client()
        response = client.post("/register", data={
            "csrf_token": token(client, "/register"), "username": name,
            "email": "other_" + name + "@example.com",
            "password": PASSWORD, "confirm_password": PASSWORD
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("already registered", response.get_data(as_text=True))

    def test_each_user_has_separate_profile_and_plan(self):
        first, first_name = self.register()
        second, _ = self.register()
        first_headers = {"X-CSRF-Token": token(first, "/")}
        second_headers = {"X-CSRF-Token": token(second, "/")}

        self.assertEqual(first.put("/api/profile", json=PROFILE, headers=first_headers).status_code, 200)
        plan = first.post("/api/recommend", headers=first_headers).get_json()

        # The second user sees nothing of the first, even when naming their id.
        self.assertEqual(second.get("/api/profile").get_json(), {"profile": None, "plan": None})
        first_id = database.find_user_by_login(first_name)["id"]
        other = dict(PROFILE, age=40, user_id=first_id)
        second.put("/api/profile", json=other, headers=second_headers)

        # A new login loads the first user's own profile and plan.
        again, _ = self.log_in(first_name, PASSWORD)
        saved = again.get("/api/profile").get_json()
        self.assertEqual(saved["profile"]["age"], 22)
        self.assertEqual(saved["plan"], plan)

        # Changing the profile removes the outdated plan.
        again.put("/api/profile", json=dict(PROFILE, age=30), headers={"X-CSRF-Token": token(again, "/")})
        self.assertIsNone(again.get("/api/profile").get_json()["plan"])

    def test_invalid_profile_is_not_saved(self):
        client, _ = self.register()
        headers = {"X-CSRF-Token": token(client, "/")}
        response = client.put("/api/profile", json={"height_cm": 165}, headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(client.get("/api/profile").get_json()["profile"])


@unittest.skipUnless(TEST_DATABASE_URL, "Set TEST_DATABASE_URL to also test PostgreSQL.")
class PostgresAccountTests(AccountTests):
    """The same tests on PostgreSQL."""

    def make_url(self):
        return TEST_DATABASE_URL


if __name__ == "__main__":
    unittest.main(verbosity=2)
