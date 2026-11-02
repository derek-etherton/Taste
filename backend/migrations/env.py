"""Alembic environment: the models in taste/storage/db.py, the database in TASTE_DATABASE_URL."""

from logging.config import fileConfig

from alembic import context

from taste.settings import get_settings
from taste.storage.db import Base, connect

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def run() -> None:
    url = config.get_main_option("sqlalchemy.url") or get_settings().database_url
    if not url:
        raise SystemExit("Set TASTE_DATABASE_URL (see README, Accounts).")
    with connect(url).connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run()
