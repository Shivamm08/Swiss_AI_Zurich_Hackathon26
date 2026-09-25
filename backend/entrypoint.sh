#!/bin/sh
# Container start: apply migrations, load the KB, then serve.
set -e
alembic upgrade head
python -m app.scripts.sync_kb
# PORT is set by hosts like Render; 8000 locally.
if [ "${UVICORN_RELOAD:-0}" = "1" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
