# Hardened Django Site

A minimal, security-hardened Django website. Public landing pages (Home / About
/ Contact), signup / login / logout built on Django's built-in auth, and a
Dashboard reachable **only** by authenticated users (enforced server-side with
`@login_required`).

Security rationale for every control lives in **[SECURITY.md](SECURITY.md)**.

## Stack
- Python 3.11+ / Django 5.2 (latest stable, LTS line)
- Django built-in auth (`django.contrib.auth`)
- Argon2 password hashing, django-axes (brute-force lockout),
  django-csp (Content-Security-Policy), django-environ (12-factor config)
- SQLite by default; swap to Postgres by setting `DATABASE_URL`

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # add -dev for pip-audit

cp .env.example .env                      # then edit .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# paste the result as SECRET_KEY in .env

python manage.py migrate
python manage.py createsuperuser          # optional, for /admin
```

### Local development over plain HTTP
The defaults force HTTPS (`SECURE_SSL_REDIRECT`, HSTS). For local HTTP testing,
put this in `.env`:

```
DEBUG=True
SECURE_SSL_REDIRECT=False
SECURE_HSTS_SECONDS=0
```

Then `python manage.py runserver`.

> Production runs with the secure defaults (`DEBUG=False`, SSL redirect + HSTS
> on) behind a TLS-terminating proxy. See SECURITY.md §8.

## Verification

```bash
python manage.py check --deploy      # -> 0 issues
python manage.py test                # -> security behavior tests
pip-audit -r requirements.txt        # -> dependency vulnerability scan
```

## Deploying to Vercel

This repo includes `vercel.json`. A single `@vercel/python` build serves
`config/wsgi.py` as a serverless function (templates are bundled via
`includeFiles`). The public pages use no static assets, so nothing else is
needed. The Django admin's CSS/JS are not collected in this minimal setup, so
`/admin/` renders unstyled but fully functional — see the static-files note in
`config/settings.py` if you want to wire those up.

### 1. Set Environment Variables (Vercel → Settings → Environment Variables)

These are **required** — the app fails closed without them (that "Failed to read
settings / KeyError: 'SECRET_KEY'" build error is exactly this safeguard):

| Variable | Value | Why |
|---|---|---|
| `SECRET_KEY` | 50+ char random string | signs sessions/CSRF/reset tokens; no default by design |
| `DEBUG` | `False` | never expose stack traces in prod |
| `ALLOWED_HOSTS` | `.vercel.app,yourdomain.com` | Host-header validation (`.vercel.app` matches all deploy URLs) |
| `USE_X_FORWARDED_PROTO` | `True` | **mandatory on Vercel** — see note below |
| `DATABASE_URL` | `postgres://USER:PASS@HOST:5432/DB` | **mandatory** — SQLite cannot run on Vercel (see below) |

Generate the secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

> **Why `USE_X_FORWARDED_PROTO=True` is mandatory:** Vercel terminates TLS at the
> edge and forwards to the function over HTTP, setting `X-Forwarded-Proto:
> https`. Without this flag Django thinks the request is plain HTTP and
> `SECURE_SSL_REDIRECT` bounces it to HTTPS forever — an **infinite redirect
> loop**. The flag tells Django to trust that header.

> **Why SQLite won't work:** Vercel functions have an ephemeral, read-only
> filesystem, so the default `db.sqlite3` can't be written and is wiped on every
> cold start. Point `DATABASE_URL` at managed Postgres (Vercel Postgres, Neon,
> Supabase, …); the project already supports it with no code change.

`SECRET_KEY` must also be present at **build** time (the static-build step
imports settings to run `collectstatic`).

### 2. Run migrations

Vercel does not run migrations (and serverless functions shouldn't). Apply them
once against your Postgres from your machine or CI:
```bash
DATABASE_URL='postgres://…' python manage.py migrate
```
Re-run after any future model/migration changes.
