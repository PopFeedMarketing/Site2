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
