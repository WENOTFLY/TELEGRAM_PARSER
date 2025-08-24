#!/bin/sh
set -e

cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd):${PYTHONPATH}"

# Run migrations with retry only for connection errors
while true; do
  if output=$(alembic upgrade head 2>&1); then
    break
  fi

  echo "$output"
  if echo "$output" | grep -qE '(Connection refused|could not connect|network is unreachable|Database .+ does not exist)'; then
    echo "Database not ready, retrying in 1s..."
    sleep 1
  else
    echo "Migration failed" >&2
    exit 1
  fi
done

# Start worker process and keep logs streaming
python - <<'PY'
import logging, time
from worker import FLOOD_WAIT_COUNTER, WORKER_ERRORS  # ensure metrics init
logging.basicConfig(level=logging.INFO)
logging.info("Worker service started")
while True:
    time.sleep(60)
    logging.info("heartbeat")
PY
