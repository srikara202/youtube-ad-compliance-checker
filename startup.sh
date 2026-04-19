#!/usr/bin/env sh
set -eu

cd /home/site/wwwroot
PACKAGE_PATH="/home/site/wwwroot/python_packages/lib/site-packages"
export PYTHONPATH="${PACKAGE_PATH}:/home/site/wwwroot${PYTHONPATH:+:${PYTHONPATH}}"

exec gunicorn \
  --bind "0.0.0.0:${PORT:-8000}" \
  --timeout "${GUNICORN_TIMEOUT:-600}" \
  --workers "${GUNICORN_WORKERS:-1}" \
  --worker-class uvicorn.workers.UvicornWorker \
  backend.src.api.server:app
