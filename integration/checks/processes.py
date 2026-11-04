"""Start, probe and stop real `-m integration.serve` launcher processes."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from integration.checks.http_client import send_http_request
from integration.workspace import CODE_ROOT, LOOPBACK_HOST

__all__ = [
    "LAUNCHER_START_TIMEOUT_SECONDS", "LOG_TAIL_CHARS",
    "LauncherProcess", "find_free_loopback_port",
]

LAUNCHER_START_TIMEOUT_SECONDS = 30  # preflight + bind + first State on a cold interpreter
LAUNCHER_STOP_TIMEOUT_SECONDS = 15  # terminate, then kill, each bounded by this
READINESS_PROBE_TIMEOUT_SECONDS = 5  # one GET /api/state while waiting for the server
READINESS_POLL_INTERVAL_SECONDS = 0.3
LOG_TAIL_CHARS = 1500  # characters of each launcher log shown in a failure detail

# Storage/crash variables stripped from the launcher's environment, so a value left
# in the caller's shell can never redirect the run state or crash the server.
LAUNCHER_STRIPPED_ENV_NAMES = frozenset({
    "RECOVERY_LEDGER", "RECOVERY_CRASH_AFTER_COMMIT", "RUMI_CONSOLE_STORAGE_ROOT", "RUMI_DATA_DIR",
})


class LauncherProcess:
    def __init__(self, storage_root: Path, port: int, log_dir: Path, label: str):
        self.storage_root, self.port, self.log_dir, self.label = storage_root, port, log_dir, label
        self.process: subprocess.Popen | None = None
        self.stdout_log_path = log_dir / f"server-{label}.out.log"
        self.stderr_log_path = log_dir / f"server-{label}.err.log"
        self._stdout_file = None
        self._stderr_file = None

    def start(self) -> subprocess.Popen:
        env = {env_name: env_value for env_name, env_value in os.environ.items()
               if env_name not in LAUNCHER_STRIPPED_ENV_NAMES}
        try:
            self._stdout_file = open(self.stdout_log_path, "wb")
            self._stderr_file = open(self.stderr_log_path, "wb")
            self.process = subprocess.Popen(
                [sys.executable, "-m", "integration.serve",
                 "--storage-root", str(self.storage_root), "--port", str(self.port)],
                cwd=str(CODE_ROOT), env=env, stdout=self._stdout_file, stderr=self._stderr_file,
            )
        except BaseException:
            self._close_log_files()
            raise
        return self.process

    def wait_until_serving(self, timeout: float = LAUNCHER_START_TIMEOUT_SECONDS) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                return False
            try:
                status, _, _ = send_http_request(self.port, "GET", "/api/state", timeout=READINESS_PROBE_TIMEOUT_SECONDS)
                if status == 200:
                    return True
            except OSError:
                pass
            time.sleep(READINESS_POLL_INTERVAL_SECONDS)
        return False

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(LAUNCHER_STOP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(LAUNCHER_STOP_TIMEOUT_SECONDS)
        self._close_log_files()

    def _close_log_files(self) -> None:
        for log_file in (self._stdout_file, self._stderr_file):
            if log_file:
                log_file.close()

    def read_log_tail(self) -> str:
        log_text = ""
        for log_path in (self.stdout_log_path, self.stderr_log_path):
            if log_path.exists():
                log_text += f"--- {log_path.name}\n" + log_path.read_text("utf-8", "replace")[-LOG_TAIL_CHARS:]
        return log_text


def find_free_loopback_port() -> int:
    with socket.socket() as probe_socket:
        probe_socket.bind((LOOPBACK_HOST, 0))
        return probe_socket.getsockname()[1]
