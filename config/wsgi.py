"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

# Vercel's @vercel/python runtime looks for a WSGI callable named ``app``.
# Alias it here so the same wsgi.py works both for a normal gunicorn/uvicorn
# deployment (which uses ``application``) and for Vercel.
app = application
