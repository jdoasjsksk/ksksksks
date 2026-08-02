#!/bin/sh
set -e

mkdir -p "$HERMES_HOME"

if [ -z "$DASHBOARD_PASSWORD" ]; then
  echo "DASHBOARD_PASSWORD belum diset, keluar."
  exit 1
fi

if [ -z "$COOKIE_SECRET" ]; then
  echo "COOKIE_SECRET belum diset, generate acak untuk sesi kali ini."
  export COOKIE_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
fi

hermes dashboard --host 127.0.0.1 --port 9119 --no-open &
HERMES_PID=$!

for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:9119/api/status >/dev/null 2>&1; then
    echo "Hermes dashboard siap"
    break
  fi
  sleep 1
done

hermes gateway start || true

cd /srv
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
