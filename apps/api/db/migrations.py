"""Very small SQLite migration helpers for the MVP."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


RUN_COLUMNS = {
    "source_repo_path": "TEXT",
    "workspace_path": "TEXT",
    "approval_status": "TEXT DEFAULT 'PENDING'",
    "user_id": "TEXT",
    "project_id": "TEXT",
    "base_run_id": "TEXT",
    "cancel_requested": "BOOLEAN DEFAULT 0",
    "request_json": "TEXT",
    "metrics_json": "TEXT",
}

FILE_CHANGE_COLUMNS = {
    "approved": "BOOLEAN",
}


def migrate_database(engine: Engine) -> None:
    inspector = inspect(engine)
    with engine.begin() as connection:
        if "runs" in inspector.get_table_names():
            existing = {column["name"] for column in inspector.get_columns("runs")}
            for column, ddl in RUN_COLUMNS.items():
                if column not in existing:
                    connection.execute(text(f"ALTER TABLE runs ADD COLUMN {column} {ddl}"))

        if "file_changes" in inspector.get_table_names():
            existing = {column["name"] for column in inspector.get_columns("file_changes")}
            for column, ddl in FILE_CHANGE_COLUMNS.items():
                if column not in existing:
                    connection.execute(text(f"ALTER TABLE file_changes ADD COLUMN {column} {ddl}"))
