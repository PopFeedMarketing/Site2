"""Tests that assert the *security* behavior, not just that pages render.

Run with:  python manage.py test

These override SECURE_SSL_REDIRECT (so the test client can speak plain HTTP)
and ALLOWED_HOSTS (for the synthetic 'testserver' host). Everything else —
auth, CSRF, axes, headers — runs exactly as configured.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()

PASSWORD = "correcthorsebattery12"  # 21 chars, passes all validators


@override_settings(ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False)
class AccessControlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password=PASSWORD)

    def test_dashboard_requires_login(self):
        """Anonymous request to /dashboard/ is redirected to the login page."""
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("login"), resp.headers["Location"])

    def test_dashboard_accessible_when_logged_in(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_login_flow(self):
        resp = self.client.post(
            reverse("login"),
            {"username": "alice", "password": PASSWORD},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], reverse("dashboard"))


@override_settings(ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False)
class AuthHardeningTests(TestCase):
    def test_login_error_is_generic_and_non_enumerating(self):
        """A wrong password and an unknown user yield the IDENTICAL error,
        so the form can't be used to enumerate valid usernames."""
        User.objects.create_user("alice", password=PASSWORD)
        bad_pw = self.client.post(
            reverse("login"), {"username": "alice", "password": "wrongwrongwrong"}
        )
        unknown = self.client.post(
            reverse("login"), {"username": "ghost", "password": "wrongwrongwrong"}
        )
        self.assertContains(bad_pw, "Please enter a correct username and password")
        self.assertContains(unknown, "Please enter a correct username and password")

    def test_short_password_rejected(self):
        """The 12-char minimum length validator rejects a short password."""
        resp = self.client.post(
            reverse("signup"),
            {"username": "bob", "password1": "short1", "password2": "short1"},
        )
        self.assertEqual(resp.status_code, 200)  # re-rendered with errors
        self.assertContains(resp, "too short")

    def test_password_is_argon2_hashed(self):
        """New passwords are stored as Argon2 hashes, never plaintext."""
        u = User.objects.create_user("carol", password=PASSWORD)
        self.assertTrue(u.password.startswith("argon2$"))
        self.assertNotIn(PASSWORD, u.password)


@override_settings(ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False)
class CsrfTests(TestCase):
    def test_post_without_csrf_token_is_rejected(self):
        """With CSRF enforcement on, a POST lacking the token is a 403."""
        csrf_client = Client(enforce_csrf_checks=True)
        resp = csrf_client.post(
            reverse("login"), {"username": "a", "password": "b"}
        )
        self.assertEqual(resp.status_code, 403)


@override_settings(ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False)
class SecurityHeaderTests(TestCase):
    def test_security_headers_present(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.headers["X-Frame-Options"], "DENY")
        self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resp.headers["Referrer-Policy"], "same-origin")
        csp = resp.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertNotIn("unsafe-inline", csp)


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    SECURE_SSL_REDIRECT=False,
    AXES_FAILURE_LIMIT=3,
)
class BruteForceLockoutTests(TestCase):
    def test_repeated_failures_trigger_lockout(self):
        """After AXES_FAILURE_LIMIT bad attempts the account/IP is locked:
        even the CORRECT password is now refused (403 lockout)."""
        User.objects.create_user("dave", password=PASSWORD)
        for _ in range(3):
            self.client.post(
                reverse("login"), {"username": "dave", "password": "nope-nope-nope"}
            )
        # Now even the right password is blocked by the lockout. django-axes
        # returns HTTP 429 Too Many Requests once the failure limit is hit.
        resp = self.client.post(
            reverse("login"), {"username": "dave", "password": PASSWORD}
        )
        self.assertEqual(resp.status_code, 429)
