#!/bin/sh
# Container start: apply migrations, load the KB, then serve.
set -e
alembic upgrade head
python -m app.scripts.sync_kb
if [ "${UVICORN_RELOAD:-0}" = "1" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
