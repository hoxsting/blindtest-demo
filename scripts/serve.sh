#!/usr/bin/env bash
# Build the React frontend and launch the FastAPI server bound to 0.0.0.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT/frontend"
echo "📦 Building frontend…"
npm run build

echo "🚚 Copying build to backend/static…"
rm -rf "$ROOT/backend/static"
mkdir -p "$ROOT/backend/static"
cp -r "$ROOT/frontend/dist/." "$ROOT/backend/static/"

cd "$ROOT/backend"
if [ ! -d ".venv" ]; then
  echo "🐍 Creating venv…"
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
fi
echo "🐍 Syncing Python dependencies…"
./.venv/bin/pip install -r requirements.txt --quiet

echo "🚀 Launching FastAPI on 0.0.0.0:8000…"
exec ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
