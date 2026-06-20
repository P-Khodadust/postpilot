#!/usr/bin/env bash
# Single image, multiple roles. Usage: entrypoint.sh <bot|web|worker|migrate>
set -euo pipefail
ROLE="${1:-web}"

case "$ROLE" in
  migrate)
    exec alembic upgrade head
    ;;
  web)
    exec gunicorn postpilot.web.app:app \
      -k uvicorn.workers.UvicornWorker \
      -b 0.0.0.0:8000 --workers "${WEB_WORKERS:-2}" --timeout 60
    ;;
  bot)
    exec python -m postpilot.bot.main
    ;;
  worker)
    exec python -m postpilot.worker.main
    ;;
  *)
    echo "Unknown role: $ROLE (expected bot|web|worker|migrate)" >&2
    exit 64
    ;;
esac
