#!/bin/sh
set -e

# Run migrations with retry until database is ready
until alembic upgrade head; do
  echo "Database not ready, retrying in 1s..."
  sleep 1
done

# Start web server
exec uvicorn web:app --host 0.0.0.0 --port "${PORT:-8000}"
