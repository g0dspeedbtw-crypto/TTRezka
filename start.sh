#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
URL="http://127.0.0.1:${PORT}"

echo "🎬 Запуск TikCut Studio на ${URL} ..."
(sleep 1.5 && open "${URL}" >/dev/null 2>&1 || true) &

exec .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port "${PORT}"
