"""Web service startup configuration."""

from migrate import upgrade_db

upgrade_db()
