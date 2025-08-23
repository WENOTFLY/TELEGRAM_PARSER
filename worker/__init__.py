"""Worker service startup configuration."""

from prometheus_client import Counter, REGISTRY, start_http_server

from logging_config import configure_logging
from migrate import upgrade_db

configure_logging()
start_http_server(8001)

try:
    FLOOD_WAIT_COUNTER = Counter(
        "flood_wait_total", "Number of FLOOD_WAIT errors encountered"
    )
except ValueError:
    FLOOD_WAIT_COUNTER = REGISTRY._names_to_collectors["flood_wait_total"]

try:
    WORKER_ERRORS = Counter("worker_errors_total", "Unhandled worker exceptions")
except ValueError:
    WORKER_ERRORS = REGISTRY._names_to_collectors["worker_errors_total"]

upgrade_db()

__all__ = ["FLOOD_WAIT_COUNTER", "WORKER_ERRORS"]
