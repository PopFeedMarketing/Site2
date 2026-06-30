# Security Design

This document explains every security control in this project: **what it is,
where it lives, and which attack it defends against.** The guiding principle is
to lean on Django's built-in, battle-tested machinery (auth, sessions, CSRF,
the ORM, template auto-escaping) rather than hand-rolling security-critical
code, and to **fail closed** when configuration is missing.

---

## 1. Authentication & passwords

### Argon2 password hashing
- **Where:** `PASSWORD_HASHERS` in `config/settings.py`, with
  `Argon2PasswordHasher` listed first; `argon2-cffi` installed.
- **Why:** If the database is ever stolen, attackers get only password
  *hashes*. Argon2 is a memory-hard function (winner of the Password Hashing
  Competition) that is deliberately expensive to brute-force on GPUs/ASICs,
  unlike fast hashes (MD5/SHA) or even PBKDF2. Listing it first means all new
  passwords use Argon2; keeping the other hashers lets Django verify and
  transparently upgrade any legacy hashes on next login.

### Password validators (min length 12)
- **Where:** `AUTH_PASSWORD_VALIDATORS` in `config/settings.py`.
- **Why:** All four validators are enabled. They reject the passwords that
  online-guessing, dictionary, and credential-stuffing attacks try first:
  too-short (< 12), too-common (against a 20k list), entirely numeric, or too
  similar to the user's own username/email.

### Session-key rotation on login
- **Where:** Django default — we do **not** disable it. `accounts/views.py`
  uses Django's `login()`.
- **Why:** Defends against **session fixation**. Django issues a fresh session
  key when a user authenticates, so a session ID an attacker planted in the
  victim's browser before login is worthless afterward.

### Generic authentication errors (no user enumeration)
- **Where:** `accounts/forms.py::HardenedAuthenticationForm`.
- **Why:** A wrong username and a wrong password produce the *same* error
  message ("Please enter a correct username and password..."). If the messages
  differed, an attacker could enumerate which usernames exist. Verified by
  `AuthHardeningTests.test_login_error_is_generic_and_non_enumerating`.

---

## 2. Sessions & CSRF

### Secure / HttpOnly / SameSite cookies
- **Where:** `SESSION_COOKIE_*` and `CSRF_COOKIE_*` in `config/settings.py`.
- **Why:**
  - `*_SECURE = True` — cookies are only ever transmitted over HTTPS, so they
    can't be captured on a plaintext network.
  - `SESSION_COOKIE_HTTPONLY = True` — JavaScript cannot read the session
    cookie, so an XSS flaw can't exfiltrate the session.
  - `*_SAMESITE = "Lax"` — the browser won't attach the cookie to most
    cross-site requests, blunting CSRF.

### CSRF middleware + `{% csrf_token %}`
- **Where:** `CsrfViewMiddleware` in `MIDDLEWARE`; `{% csrf_token %}` on every
  POST form (login, signup, logout).
- **Why:** Defends against **Cross-Site Request Forgery**. Without the
  per-session token, a malicious site could trick a logged-in user's browser
  into submitting state-changing requests. Logout is a POST (not GET) for the
  same reason. Verified by `CsrfTests.test_post_without_csrf_token_is_rejected`.

---

## 3. Transport & response headers

| Setting | Defends against |
|---|---|
| `SECURE_SSL_REDIRECT = True` | Plaintext eavesdropping — every HTTP request is 301'd to HTTPS. |
| `SECURE_HSTS_SECONDS = 31536000` + `INCLUDE_SUBDOMAINS` + `PRELOAD` | SSL-strip / protocol-downgrade — browsers refuse plain HTTP to this domain (and subdomains) for a year. |
| `SECURE_CONTENT_TYPE_NOSNIFF = True` | MIME-sniffing — stops a browser from reinterpreting a response as executable script. |
| `X_FRAME_OPTIONS = "DENY"` | Clickjacking — the site can't be embedded in a frame. |
| `SECURE_REFERRER_POLICY = "same-origin"` | Information leakage — full URLs (which may carry IDs/tokens) aren't sent to other origins. |

> **HSTS caveat:** `includeSubDomains` + `preload` is a strong, *sticky*
> commitment. Only serve it once every subdomain is HTTPS-ready, because
> browsers will cache the policy for a year.

### Content-Security-Policy (django-csp)
- **Where:** `CONTENT_SECURITY_POLICY` in `config/settings.py`;
  `csp.middleware.CSPMiddleware` in `MIDDLEWARE`.
- **Why:** A strict CSP is the **second line of defense against XSS** (template
  auto-escaping is the first). `default-src 'self'` allows resources only from
  our own origin, and `script-src 'self'` (with **no** `'unsafe-inline'` /
  `'unsafe-eval'`) means an injected `<script>` or inline handler simply will
  not execute. `frame-ancestors 'none'` reinforces the clickjacking defense and
  `form-action 'self'` stops an injected form from posting credentials offsite.
  Verified by `SecurityHeaderTests`.

---

## 4. Injection & output encoding

### ORM-only data access
- **Where:** Throughout. No raw SQL anywhere.
- **Why:** The Django ORM parameterizes every query, so user input is never
  concatenated into a SQL string — **no SQL injection.**

### Template auto-escaping
- **Where:** Django templates; `|safe`/`mark_safe` are never used on
  user-controlled data.
- **Why:** Every variable rendered into HTML is escaped, neutralizing injected
  markup/script — the primary defense against **stored/reflected XSS.**

---

## 5. Brute-force protection (django-axes)

- **Where:** `axes` app + `AxesStandaloneBackend` (first auth backend) +
  `AxesMiddleware` (last middleware); `AXES_*` settings in `config/settings.py`.
- **Why:** Defends against **online password guessing & credential stuffing.**
  Config rationale:
  - `AXES_FAILURE_LIMIT = 5` — lock after 5 consecutive failures.
  - `AXES_COOLOFF_TIME = 1` (hour) — the lock auto-expires, so a real user who
    mistypes isn't locked out forever and no manual unlock is needed.
  - `AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]` — we lock the
    *combination*. Locking by IP alone lets one attacker behind shared NAT lock
    out everyone; locking by username alone lets an attacker deliberately lock a
    victim out of their own account (a DoS). Locking the pair balances both.
  - `AXES_RESET_ON_SUCCESS = True` — a good login clears the failure counter.
  - The backend is placed **first** so a locked-out attempt is rejected before
    the password is ever checked; the middleware is **last** so it sees the
    final auth outcome. A locked request gets HTTP **429 Too Many Requests**.
    Verified by `BruteForceLockoutTests`.

---

## 6. Secrets & configuration (django-environ)

- **Where:** `config/settings.py` reads `SECRET_KEY`, `DEBUG`,
  `ALLOWED_HOSTS`, `DATABASE_URL` from the environment; `.env.example` is the
  template; real `.env` is in `.gitignore`.
- **Why:**
  - **Secrets never enter source control.** `SECRET_KEY` has *no default* — a
    missing key crashes startup rather than booting with a guessable key (it
    signs sessions, password-reset and CSRF tokens).
  - **`DEBUG` defaults to `False`.** A forgotten env var can't accidentally
    expose stack traces, settings and SQL to visitors.
  - **`ALLOWED_HOSTS` defaults to empty,** so unknown Host headers are rejected
    — defeating Host-header poisoning and cache-poisoning.
  - **DB is a URL.** Switching SQLite → Postgres is `DATABASE_URL=postgres://…`
    with zero code change.

---

## 7. Verification performed

- `python manage.py check --deploy` → **0 issues.**
- `pip-audit -r requirements.txt` → **no known vulnerabilities.**
- `python manage.py test` → **9 passing** security/behavior tests.
- All dependencies are pinned to exact versions in `requirements.txt`.

---

## 8. NOT handled here — must be addressed at deploy/infra layer

This application code is hardened, but a secure *deployment* additionally
requires (none of these can be solved inside this repo):

- **TLS termination & certificates.** Django sets HSTS and redirects to HTTPS,
  but an actual TLS cert (e.g. via a load balancer / reverse proxy / Let's
  Encrypt) must terminate HTTPS in front of the app. Set
  `USE_X_FORWARDED_PROTO=True` when behind such a proxy.
- **Where secrets actually live.** `.env` is fine for local dev; production
  secrets belong in a secrets manager (AWS Secrets Manager, Vault, GCP Secret
  Manager, etc.), not a file on disk.
- **OS / server / dependency patching.** Keep the OS, Python, and pinned
  dependencies updated; re-run `pip-audit` in CI.
- **DDoS / rate limiting at the edge.** Axes throttles *login* attempts only.
  Volumetric and application-layer DDoS need a CDN/WAF (Cloudflare, AWS
  Shield/WAF, etc.).
- **Email verification.** Signup does not verify email ownership.
- **Multi-factor authentication (MFA/2FA).** Not implemented; add e.g.
  `django-otp` / `django-two-factor-auth` for accounts that need it.
- **Production static-file serving & a hardened WSGI/ASGI server** (gunicorn/
  uvicorn behind nginx), with the app server never exposed directly.
- **Logging, monitoring & alerting** for the axes lockout events and auth
  failures.
- **Database security:** encryption at rest, network isolation, least-privilege
  DB credentials, and backups.
- **Security headers not expressible in app code** that some orgs add at the
  edge (e.g. Permissions-Policy), and CSP violation reporting endpoints.
