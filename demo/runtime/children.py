"""Fresh worker child processes: environment, bounded execution, JSON stdout parsing."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from demo.runtime.contract import (
    CHILD_TIMEOUT_SECONDS, CODE_ROOT, CRASH_ENV, LEDGER_ENV, RUMI_SRC, STDERR_TAIL_CHARS,
    STORAGE_ROOT_ENV, WORKER_CRASH, ledger_path,
)

__all__ = [
    "ChildProcessFailure", "build_child_env",
    "run_worker_phase", "stderr_tail", "run_child_for_json",
]


class ChildProcessFailure(Exception):
    """A worker child timed out, could not start, or produced unusable output."""

    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def build_child_env(storage_root, run_dir: Path, crash_after_commit: bool) -> dict:
    """Child-only environment; the server's own os.environ is never modified."""
    env = dict(os.environ)
    env.pop(CRASH_ENV, None)
    python_path_entries = [str(CODE_ROOT), str(RUMI_SRC)]
    if env.get("PYTHONPATH"):
        python_path_entries.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path_entries)
    env[LEDGER_ENV] = str(ledger_path(run_dir))
    env[STORAGE_ROOT_ENV] = str(Path(storage_root).resolve())
    if crash_after_commit:
        env[CRASH_ENV] = "1"
    return env


def run_worker_phase(storage_root, run_dir: Path, phase: str) -> subprocess.CompletedProcess:
    """Run ``python -m demo.worker <phase> <run_dir>`` and block until it exits (or times out)."""
    try:
        return subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "demo.worker", phase, str(run_dir)],
            cwd=str(CODE_ROOT), env=build_child_env(storage_root, run_dir, phase == WORKER_CRASH),
            capture_output=True, timeout=CHILD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ChildProcessFailure("worker_timeout", f"{phase} exceeded {CHILD_TIMEOUT_SECONDS}s") from exc
    except OSError as exc:
        raise ChildProcessFailure("worker_failed", f"could not start {phase}: {exc}") from exc


def stderr_tail(completed_process) -> str:
    return (completed_process.stderr or b"").decode("utf-8", "replace").strip()[-STDERR_TAIL_CHARS:]


def run_child_for_json(storage_root, run_dir: Path, phase: str, failure_code: str) -> dict:
    """Run a phase that must exit 0 and print exactly one JSON object on stdout."""
    completed_process = run_worker_phase(storage_root, run_dir, phase)
    text = (completed_process.stdout or b"").decode("utf-8", "replace").strip()
    if completed_process.returncode != 0:
        raise ChildProcessFailure(
            failure_code, f"{phase} exited {completed_process.returncode}: {stderr_tail(completed_process)}")
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ChildProcessFailure(
            failure_code, f"{phase} produced no JSON: {stderr_tail(completed_process)}") from exc
    if not isinstance(data, dict):
        raise ChildProcessFailure(failure_code, f"{phase} produced non-object JSON")
    return data
