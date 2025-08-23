import json
import logging
import contextvars
from typing import Optional

user_id_var: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("user_id", default=None)
session_id_var: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("session_id", default=None)


class JsonFormatter(logging.Formatter):
    """Format logs as JSON with user and session context."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - short
        data = {
            "level": record.levelname,
            "message": record.getMessage(),
        }
        user_id = user_id_var.get()
        if user_id is not None:
            data["user_id"] = user_id
        session_id = session_id_var.get()
        if session_id is not None:
            data["session_id"] = session_id
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(data)


def configure_logging() -> None:
    """Configure root logging to use JSON formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
