#!/usr/bin/env sh
set -eu

cd /home/site/wwwroot
export PYTHONPATH="${PYTHONPATH:-/home/site/wwwroot}"

exec gunicorn \
  --bind "0.0.0.0:${PORT:-8000}" \
  --timeout "${GUNICORN_TIMEOUT:-600}" \
  --workers "${GUNICORN_WORKERS:-1}" \
  --worker-class uvicorn.workers.UvicornWorker \
  backend.src.api.server:app
