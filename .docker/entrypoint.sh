#!/bin/sh
set -eu

cd /app

required_vars="SECRET_KEY POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_HOST POSTGRES_PORT"
for var_name in $required_vars; do
    eval "var_value=\${$var_name:-}"
    if [ -z "$var_value" ]; then
        echo "Missing required environment variable: $var_name" >&2
        exit 1
    fi
done

if [ "${WAIT_FOR_DB:-1}" = "1" ]; then
    python - <<'PY'
import os
import socket
import sys
import time

host = os.environ["POSTGRES_HOST"]
port = int(os.environ.get("POSTGRES_PORT", "5432"))
timeout = int(os.environ.get("DB_WAIT_TIMEOUT", "60"))
deadline = time.time() + timeout
last_error = None

while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=5):
            print(f"Database is reachable at {host}:{port}", flush=True)
            break
    except OSError as exc:
        last_error = exc
        print(f"Waiting for database at {host}:{port}...", flush=True)
        time.sleep(2)
else:
    print(
        f"Database was not reachable after {timeout} seconds: {last_error}",
        file=sys.stderr,
    )
    sys.exit(1)
PY
fi

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    python manage.py migrate --noinput
fi

if [ "${COLLECT_STATIC:-1}" = "1" ]; then
    python manage.py collectstatic --noinput
fi

if [ "${RUN_DEPLOY_CHECK:-0}" = "1" ]; then
    python manage.py check --deploy --fail-level WARNING
fi

if [ "$#" -eq 0 ]; then
    set -- \
        gunicorn horilla.asgi:application \
        -k uvicorn.workers.UvicornWorker \
        --bind "0.0.0.0:${PORT:-8000}" \
        --workers "${WEB_CONCURRENCY:-3}" \
        --timeout "${GUNICORN_TIMEOUT:-120}" \
        --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-30}" \
        --keep-alive "${GUNICORN_KEEP_ALIVE:-5}" \
        --access-logfile - \
        --error-logfile -
fi

exec "$@"
