"""
Django settings for the security-hardened demo site.

Design notes
------------
Every security-relevant setting below is annotated with the *why*: the attack
it defends against or the principle it upholds. Configuration that varies
between environments (secrets, hostnames, database) is read from environment
variables via django-environ so that NO secret ever lives in source control and
swapping SQLite -> Postgres is a pure ops change with zero code edits.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------
# We declare types + safe defaults up front. Anything security-sensitive
# (DEBUG, the SSL/HSTS toggles) defaults to the *secure* value, so a forgotten
# env var fails closed, not open.
env = environ.Env(
    DEBUG=(bool, False),  # fail closed: never run with DEBUG on by accident
    ALLOWED_HOSTS=(list, []),
    SECURE_SSL_REDIRECT=(bool, True),
    SECURE_HSTS_SECONDS=(int, 31536000),  # 1 year
)

# Read a local .env file if present. In production the values come from real
# environment variables instead; .env is git-ignored and never deployed.
environ.Env.read_env(BASE_DIR / ".env")

# SECRET_KEY signs sessions, password-reset tokens and CSRF tokens. If it
# leaks, an attacker can forge any of those. So it has NO default and must be
# supplied via the environment; a missing key raises ImproperlyConfigured and
# the app refuses to boot rather than running with a guessable key.
SECRET_KEY = env("SECRET_KEY")

# DEBUG must be False in production: when True Django serves verbose stack
# traces that leak source code, settings and SQL to any visitor.
DEBUG = env("DEBUG")

# Host header validation. An empty list (the default) means Django rejects all
# requests unless hosts are explicitly allow-listed, defeating Host-header
# poisoning / cache-poisoning and password-reset-link hijacking.
ALLOWED_HOSTS = env("ALLOWED_HOSTS")


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party security apps
    "axes",  # brute-force throttling / account lockout
    # First-party apps
    "pages",
    "accounts",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
# Order matters. SecurityMiddleware is first so its header/redirect logic runs
# before anything else. CSPMiddleware attaches the Content-Security-Policy
# header to every response. AxesMiddleware must be LAST so it can observe the
# final outcome of the auth pipeline and record failed login attempts.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # CSRF protection on all POSTs
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",  # clickjacking
    "csp.middleware.CSPMiddleware",  # Content-Security-Policy header
    "axes.middleware.AxesMiddleware",  # brute-force lockout (must be last)
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            # NOTE: Django template auto-escaping is ON by default and we never
            # disable it. Every variable rendered into HTML is escaped, which is
            # our primary defense against stored/reflected XSS. We never use
            # |safe or mark_safe on user-controlled data.
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# DATABASE_URL is parsed by django-environ. Default is local SQLite; setting
# DATABASE_URL=postgres://user:pass@host:5432/db in the environment switches to
# Postgres with no code change. We use the ORM exclusively (parameterized
# queries) so user input is never concatenated into SQL -> no SQL injection.
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}


# ---------------------------------------------------------------------------
# Authentication backends
# ---------------------------------------------------------------------------
# AxesStandaloneBackend must come FIRST so it can short-circuit a login attempt
# from a locked-out user/IP before Django's ModelBackend ever checks the
# password. ModelBackend then does the normal credential check.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
# Argon2 is the current best-practice memory-hard password hash; it is the
# winner of the Password Hashing Competition and resists GPU/ASIC cracking far
# better than PBKDF2. Listing it FIRST makes it the algorithm used for all new
# hashes, while keeping the others lets Django transparently verify (and
# upgrade) any legacy hashes on next login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# ---------------------------------------------------------------------------
# Password validators
# ---------------------------------------------------------------------------
# All four built-in validators are enabled. Together they block the weakest,
# most-guessable passwords (too short, too common, all-numeric, or derived from
# the user's own attributes) — the passwords credential-stuffing and dictionary
# attacks target first. Minimum length is raised to 12.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Auth flow URLs
# ---------------------------------------------------------------------------
# Where @login_required sends anonymous users, and where login/logout land.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"


# ---------------------------------------------------------------------------
# Session & CSRF cookie hardening
# ---------------------------------------------------------------------------
# Secure: cookie is only ever sent over HTTPS, so it can't be sniffed on a
# plaintext connection.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HttpOnly: the session cookie is invisible to JavaScript, so an XSS bug can't
# read it and exfiltrate the user's session.
SESSION_COOKIE_HTTPONLY = True

# SameSite=Lax: the browser won't attach these cookies to most cross-site
# requests, blunting CSRF. (We also keep Django's CSRF token middleware on as
# defense in depth — SameSite is not a complete CSRF defense on its own.)
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Django rotates the session key on login by default (we do NOT disable
# rotation), which prevents session-fixation: a session id captured before
# authentication is useless afterward.


# ---------------------------------------------------------------------------
# Transport security & response headers
# ---------------------------------------------------------------------------
# Redirect every plain-HTTP request to HTTPS.
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")

# Trust the X-Forwarded-Proto header set by a TLS-terminating proxy so Django
# knows the original request was HTTPS. Only safe because in production a
# trusted proxy (load balancer) sets this header; never expose the app server
# directly. Enable by setting USE_X_FORWARDED_PROTO=True in that environment.
if env.bool("USE_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS tells browsers "only ever talk to me over HTTPS for the next year",
# defeating SSL-strip / downgrade attacks after the first visit.
# includeSubDomains and preload extend that promise to subdomains and the
# browser preload list.
SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS")
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Stop browsers from MIME-sniffing a response into a different content type,
# which can turn an uploaded/served file into executable script.
SECURE_CONTENT_TYPE_NOSNIFF = True

# Refuse to be embedded in any <frame>/<iframe>: anti-clickjacking.
X_FRAME_OPTIONS = "DENY"

# Don't leak the full URL (which may contain ids/tokens) to other origins in
# the Referer header.
SECURE_REFERRER_POLICY = "same-origin"


# ---------------------------------------------------------------------------
# Content Security Policy (django-csp 4.x dict-based config)
# ---------------------------------------------------------------------------
# A strict CSP is our second line of defense against XSS (auto-escaping is the
# first). default-src 'self' means the browser only loads resources from our
# own origin. We deliberately omit 'unsafe-inline'/'unsafe-eval' from script-src
# so inline <script> and eval() are blocked — an injected <script> simply won't
# run. frame-ancestors 'none' is the modern equivalent of X-Frame-Options DENY,
# and form-action 'self' stops injected forms from posting credentials offsite.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'"],  # no inline scripts, no eval
        "style-src": ["'self'"],
        "img-src": ["'self'"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "base-uri": ["'self'"],  # block <base> tag hijacking
        "form-action": ["'self'"],  # forms may only submit to our origin
        "frame-ancestors": ["'none'"],  # anti-clickjacking
        "object-src": ["'none'"],  # no Flash/legacy plugins
    },
}


# ---------------------------------------------------------------------------
# django-axes: brute-force / credential-stuffing protection
# ---------------------------------------------------------------------------
# Axes records failed logins and locks out further attempts once a threshold is
# crossed, defeating online password-guessing and credential stuffing.
#
#  - FAILURE_LIMIT 5: lock after 5 consecutive failures.
#  - COOLOFF_TIME 1 (hour): the lock auto-expires after an hour, so a real user
#    who fat-fingers their password isn't locked out forever (and we don't need
#    a manual unlock workflow for the common case).
#  - LOCKOUT by (username + IP): we lock the *combination*, not the IP alone
#    (which would let one attacker behind a shared NAT lock out everyone) and
#    not the username alone (which would let an attacker lock a victim out of
#    their own account as a denial-of-service). Locking the pair balances both.
#  - RESET_ON_SUCCESS: a successful login clears that user's failure counter.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "accounts/lockout.html"
