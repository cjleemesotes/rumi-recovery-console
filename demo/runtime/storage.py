"""Run storage: paths under ``<storage_root>/.rumi-console``, run.json, the fixture ledger."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

from demo.runtime.contract import (
    AGENT_ID, AGENT_TYPE, CALL_ID, CRASH_EXIT_CODE, FILE_REPLACE_ATTEMPTS,
    FILE_REPLACE_RETRY_DELAY_SECONDS, TOOL_NAME, DemoError, is_expected_arguments,
    is_valid_run_id, manifest_path, runs_dir,
)
from demo.runtime.state import unavailable_state

__all__ = [
    "run_directory", "write_json_atomically", "load_manifest",
    "save_manifest_update", "create_payments_ledger",
]


def run_directory(storage_root, run_id: str) -> Path:
    """Directory of a run; rejects anything that is not a 32-char lowercase hex id."""
    if not is_valid_run_id(run_id):
        raise DemoError("invalid_request")
    return runs_dir(storage_root) / run_id


def write_json_atomically(path: Path, data: dict) -> None:
    temp_path = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        for attempt in range(FILE_REPLACE_ATTEMPTS):
            try:
                os.replace(temp_path, path)
                return
            except PermissionError:
                if attempt == FILE_REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(FILE_REPLACE_RETRY_DELAY_SECONDS)
    except OSError as exc:
        raise DemoError("storage_failed", f"Could not write {path.name}: {exc}") from exc
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def load_manifest(storage_root, run_id: str) -> dict:
    """Read run.json and refuse contradictory or type-loose metadata."""
    run_dir = run_directory(storage_root, run_id)
    path = manifest_path(run_dir)
    if not run_dir.is_dir() or not path.is_file():
        raise DemoError("unknown_run")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DemoError("storage_failed", f"Could not read run.json: {exc}") from exc
    if not isinstance(data, dict) or data.get("run_id") != run_id:
        raise DemoError("storage_failed", "run.json does not match this run.")
    exit_code = data.get("worker_exit_code")
    request_id = data.get("request_idea_id")
    version = data.get("version")
    consistent = (
        type(version) is int and version == 1 and is_expected_arguments(data.get("arguments"))
        and data.get("agent_type") == AGENT_TYPE
        and data.get("agent_id") == AGENT_ID and data.get("tool_call_id") == CALL_ID
        and data.get("tool_name") == TOOL_NAME
        and (exit_code is None or (type(exit_code) is int and exit_code == CRASH_EXIT_CODE))
        and (request_id is None or isinstance(request_id, str))
    )
    if not consistent:
        raise DemoError("demo_identity_mismatch", state=unavailable_state(
            {"run_id": run_id}, "demo_identity_mismatch", "run.json metadata is contradictory"))
    return data


def save_manifest_update(storage_root, manifest: dict, **changes) -> dict:
    manifest = {**manifest, **changes}
    write_json_atomically(manifest_path(run_directory(storage_root, manifest["run_id"])), manifest)
    return manifest


def create_payments_ledger(path: Path) -> None:
    """Create the unchanged fixture table (no primary key)."""
    try:
        conn = sqlite3.connect(str(path))
        try:
            conn.execute("CREATE TABLE payments (order_id TEXT NOT NULL, amount INTEGER NOT NULL)")
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise DemoError("storage_failed", f"Could not create the ledger: {exc}") from exc
