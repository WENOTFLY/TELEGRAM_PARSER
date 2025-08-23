"""Utilities for database migrations."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from config import settings


def upgrade_db() -> None:
    """Run Alembic upgrade to the latest revision."""
    cfg = Config(str(Path(__file__).with_name("alembic.ini")))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
