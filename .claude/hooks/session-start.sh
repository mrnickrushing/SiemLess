#!/bin/bash
# SiemLess session-start hook
# Installs all dependencies and starts the backend + frontend dev servers
# for Claude Code on the web sessions.
set -euo pipefail

# Only run in remote (web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo '{"async": true, "asyncTimeout": 300000}'

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/home/user/SiemLess}"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# ---------------------------------------------------------------------------
# Environment variables — written to $CLAUDE_ENV_FILE so they persist for
# the whole session (including when uvicorn is later invoked by the platform).
# ---------------------------------------------------------------------------
cat >> "$CLAUDE_ENV_FILE" << 'EOF'
export DEBUG=true
export SECRET_KEY=dev-secret-key-siemless-not-for-production
export ADMIN_PASSWORD=siemless
export DATABASE_URL=sqlite+aiosqlite:///./dev.db
EOF

# Source them now so they're available in this script too
export DEBUG=true
export SECRET_KEY=dev-secret-key-siemless-not-for-production
export ADMIN_PASSWORD=siemless
export DATABASE_URL=sqlite+aiosqlite:///./dev.db

# ---------------------------------------------------------------------------
# Backend — Python dependencies
# ---------------------------------------------------------------------------
echo "[session-start] Installing backend Python dependencies..."
pip install --quiet --no-warn-script-location \
  -r "$BACKEND_DIR/requirements.txt" \
  -r "$BACKEND_DIR/requirements-dev.txt"

# Extra packages needed in this container environment
pip install --quiet --no-warn-script-location aiosqlite cffi pytest-env

echo "[session-start] Backend dependencies installed."

# ---------------------------------------------------------------------------
# Backend — start uvicorn in background
# ---------------------------------------------------------------------------
echo "[session-start] Starting backend (uvicorn)..."
cd "$BACKEND_DIR"
nohup uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  > /tmp/siemless-backend.log 2>&1 &
echo "[session-start] Backend started (PID $!, log: /tmp/siemless-backend.log)"

# ---------------------------------------------------------------------------
# Frontend — npm dependencies
# ---------------------------------------------------------------------------
echo "[session-start] Installing frontend npm dependencies..."
cd "$FRONTEND_DIR"
npm install --silent

echo "[session-start] Frontend dependencies installed."

# ---------------------------------------------------------------------------
# Frontend — start Vite dev server in background
# ---------------------------------------------------------------------------
echo "[session-start] Starting frontend (Vite)..."
nohup npm run dev -- --host 0.0.0.0 --port 5173 \
  > /tmp/siemless-frontend.log 2>&1 &
echo "[session-start] Frontend started (PID $!, log: /tmp/siemless-frontend.log)"

echo "[session-start] SiemLess ready — backend :8000, frontend :5173"
