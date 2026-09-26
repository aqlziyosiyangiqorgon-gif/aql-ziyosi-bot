"""Alembic migration runner."""

import os

from alembic.config import Config

from alembic import command


def run_upgrade_head(config_path: str = "alembic.ini") -> None:
    """Run Alembic migrations programmatically to head."""
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Alembic configuration file not found at {config_path}")
    alembic_cfg = Config(config_path)
    command.upgrade(alembic_cfg, "head")
