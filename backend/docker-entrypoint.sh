#!/bin/sh
set -e

echo "[entrypoint] Running Alembic migrations…"
python -m alembic upgrade head
echo "[entrypoint] Migrations complete. Starting uvicorn…"

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
