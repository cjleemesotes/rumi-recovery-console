"""Read and deliberately tamper with one isolated run's files (history, ledger, run.json)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from rumi.tablet.filesystem import FilesystemTablet

from integration.checks.expectations import AGENT_ID, AGENT_TYPE

__all__ = [
    "execute_ledger_sql", "ledger_path", "open_history_tablet", "read_history_entries",
    "read_history_file_bytes", "read_ledger_rows", "read_run_manifest",
    "run_directory", "run_manifest_path", "runs_directory",
]


def runs_directory(storage_root: Path) -> Path:
    return storage_root / ".rumi-console" / "runs"


def run_directory(storage_root: Path, run_id: str) -> Path:
    return runs_directory(storage_root) / run_id


def ledger_path(storage_root: Path, run_id: str) -> Path:
    return run_directory(storage_root, run_id) / "ledger.sqlite3"


def run_manifest_path(storage_root: Path, run_id: str) -> Path:
    return run_directory(storage_root, run_id) / "run.json"


def open_history_tablet(storage_root: Path, run_id: str) -> FilesystemTablet:
    return FilesystemTablet(run_directory(storage_root, run_id) / "rumi", AGENT_TYPE, AGENT_ID)


def read_history_entries(storage_root: Path, run_id: str) -> list[dict]:
    history_tablet = open_history_tablet(storage_root, run_id)
    entries = [history_tablet.get(history_key) for history_key in history_tablet.list_keys("history/")]
    entries = [entry for entry in entries if entry]
    return sorted(entries, key=lambda entry: (entry.get("timestamp", 0), entry.get("seq", 0), entry.get("id", "")))


def _read_tree_bytes(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {str(file_path.relative_to(root)): file_path.read_bytes() for file_path in sorted(root.rglob("*")) if file_path.is_file()}


def read_history_file_bytes(storage_root: Path, run_id: str) -> dict[str, bytes]:
    return _read_tree_bytes(run_directory(storage_root, run_id) / "rumi")


def read_ledger_rows(storage_root: Path, run_id: str) -> list[tuple]:
    connection = sqlite3.connect(str(ledger_path(storage_root, run_id)))
    try:
        return connection.execute("SELECT order_id, amount FROM payments ORDER BY rowid").fetchall()
    finally:
        connection.close()


def execute_ledger_sql(storage_root: Path, run_id: str, sql: str, params: tuple = ()) -> None:
    connection = sqlite3.connect(str(ledger_path(storage_root, run_id)))
    try:
        connection.execute(sql, params)
        connection.commit()
    finally:
        connection.close()


def read_run_manifest(storage_root: Path, run_id: str) -> dict:
    return json.loads(run_manifest_path(storage_root, run_id).read_text("utf-8"))
