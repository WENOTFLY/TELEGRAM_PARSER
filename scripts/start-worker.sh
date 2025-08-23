#!/bin/sh
set -e

# Run migrations with retry until database is ready
until alembic upgrade head; do
  echo "Database not ready, retrying in 1s..."
  sleep 1
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
