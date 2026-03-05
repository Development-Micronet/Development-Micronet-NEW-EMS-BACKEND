#!/bin/bash
set -euo pipefail

echo "Waiting for database to be ready..."
python3 manage.py migrate --noinput
# Ensure tables are created for installed apps without migration files.
python3 manage.py migrate --run-syncdb --noinput
python3 manage.py verify_schema_tables
python3 manage.py collectstatic --noinput
gunicorn --bind 0.0.0.0:8000 horilla.wsgi:application
