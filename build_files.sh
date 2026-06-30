#!/usr/bin/env bash
# Vercel static-build step.
#
# The @vercel/python builder installs requirements and bundles the WSGI app,
# but it does NOT run collectstatic. So this separate @vercel/static-build step
# installs Django and runs collectstatic, writing the collected assets into
# STATIC_ROOT (staticfiles_build/static/). vercel.json's distDir is
# "staticfiles_build", whose contents Vercel serves at the site root, and the
# "/static/(.*)" route maps incoming /static/ requests onto them.
#
# Requires SECRET_KEY to be set in the Vercel build environment (settings import
# fails closed without it). collectstatic touches no database, so the default
# SQLite DATABASE_URL is fine here even though the running app uses Postgres.
set -o errexit  # abort the build if any command fails

pip3 install -r requirements.txt
python3 manage.py collectstatic --noinput --clear
