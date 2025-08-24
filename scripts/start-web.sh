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

# Start web server
exec uvicorn web:app --host 0.0.0.0 --port "${PORT:-8000}"
