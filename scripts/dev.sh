#!/usr/bin/env bash
# Dev mode: FastAPI (port 8000) + Vite (port 5173) in parallel, both with hot reload
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT/backend"
if [ ! -d ".venv" ]; then
  echo "🐍 Creating venv and installing requirements…"
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi

cleanup() {
  echo "🛑 Stopping…"
  kill "$BACK_PID" "$FRONT_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "🚀 Backend on http://localhost:8000"
./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACK_PID=$!

cd "$ROOT/frontend"
if [ ! -d "node_modules" ]; then
  echo "📦 Installing frontend dependencies…"
  npm install
fi
echo "🚀 Frontend on http://localhost:5173"
npm run dev &
FRONT_PID=$!

wait
