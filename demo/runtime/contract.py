"""Constants and the error type shared by the parent runtime, the workers and Cashier.

Pure standard library: safe to import without Rumi. Values here are part of the
persisted/wire contract (run.json, environment names, error codes); change with care.
"""
from __future__ import annotations

import re
from pathlib import Path

__all__ = [
    "CODE_ROOT", "RUMI_SRC", "SCHEMA_VERSION",
    "AGENT_TYPE", "AGENT_ID", "CALL_ID", "TOOL_NAME",
    "EXPECTED_ARGUMENTS", "EXPECTED_CONFIRMED_RESULT", "CRASH_EXIT_CODE",
    "LEDGER_ENV", "CRASH_ENV", "STORAGE_ROOT_ENV", "RUN_ID_PATTERN", "is_valid_run_id",
    "WORKER_CRASH", "WORKER_INSPECT", "WORKER_RECOVER", "WORKER_PHASES",
    "PHASE_IDLE", "PHASE_PENDING", "PHASE_RECOVERED", "PHASE_UNRESOLVED",
    "PHASE_UNSUPPORTED", "PHASE_ERROR",
    "console_dir", "runs_dir", "active_run_path", "manifest_path", "ledger_path", "tablet_dir",
    "is_expected_arguments", "record_error_code",
    "FILE_REPLACE_ATTEMPTS", "FILE_REPLACE_RETRY_DELAY_SECONDS", "LEDGER_READ_TIMEOUT_SECONDS",
    "CHILD_TIMEOUT_SECONDS", "STDERR_TAIL_CHARS",
    "ERROR_DEFINITIONS", "ERROR_MESSAGES", "PHASE_BY_ERROR_CODE", "HTTP_STATUS_BY_ERROR_CODE",
    "is_expected_confirmed_result", "DemoError",
]

# demo/runtime/contract.py -> runtime -> demo -> code root
CODE_ROOT = Path(__file__).resolve().parents[2]
RUMI_SRC = CODE_ROOT / "Rumi" / "src"
SCHEMA_VERSION = 1

# Persisted identity of the demo agent and its single tool call.
AGENT_TYPE = "demo.cashier.Cashier"
AGENT_ID = "till-1"
CALL_ID = "call_pay_1"
TOOL_NAME = "record_payment"
EXPECTED_ARGUMENTS = {"order_id": "A-1", "amount": 42}
EXPECTED_CONFIRMED_RESULT = {"order_id": "A-1", "amount": 42, "status": "recorded"}
CRASH_EXIT_CODE = 17

# Child-only environment variable names.
LEDGER_ENV = "RECOVERY_LEDGER"
CRASH_ENV = "RECOVERY_CRASH_AFTER_COMMIT"
STORAGE_ROOT_ENV = "RUMI_CONSOLE_STORAGE_ROOT"

RUN_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


def is_valid_run_id(value) -> bool:
    """A run id is exactly 32 lowercase hex characters (no trailing newline)."""
    return isinstance(value, str) and RUN_ID_PATTERN.fullmatch(value) is not None


# Timing/size policy.
CHILD_TIMEOUT_SECONDS = 15           # each worker child is killed after this long
FILE_REPLACE_ATTEMPTS = 10           # os.replace retries (Windows may briefly deny access)
FILE_REPLACE_RETRY_DELAY_SECONDS = 0.05
LEDGER_READ_TIMEOUT_SECONDS = 5      # SQLite busy timeout for the read-only ledger open
STDERR_TAIL_CHARS = 400              # how much child stderr is quoted in error details

# Worker child phases (the `python -m demo.worker <phase>` commands).
WORKER_CRASH = "crash"
WORKER_INSPECT = "inspect"
WORKER_RECOVER = "recover"
WORKER_PHASES = (WORKER_CRASH, WORKER_INSPECT, WORKER_RECOVER)

# State "phase" values returned to the backend and shown by the UI.
PHASE_IDLE = "idle"
PHASE_PENDING = "pending"
PHASE_RECOVERED = "recovered"
PHASE_UNRESOLVED = "unresolved"
PHASE_UNSUPPORTED = "unsupported"
PHASE_ERROR = "error"

# On-disk layout, relative to a storage root. Defined once; every module derives paths here.
_CONSOLE_DIRNAME = ".rumi-console"
_RUNS_DIRNAME = "runs"
_ACTIVE_RUN_FILENAME = "active.json"
_MANIFEST_FILENAME = "run.json"
_LEDGER_FILENAME = "ledger.sqlite3"
_TABLET_DIRNAME = "rumi"


def console_dir(storage_root) -> Path:
    return Path(storage_root).resolve() / _CONSOLE_DIRNAME


def runs_dir(storage_root) -> Path:
    return console_dir(storage_root) / _RUNS_DIRNAME


def active_run_path(storage_root) -> Path:
    return console_dir(storage_root) / _ACTIVE_RUN_FILENAME


def manifest_path(run_dir: Path) -> Path:
    return run_dir / _MANIFEST_FILENAME


def ledger_path(run_dir: Path) -> Path:
    return run_dir / _LEDGER_FILENAME


def tablet_dir(run_dir: Path) -> Path:
    """Rumi data_dir for the run's Cashier history."""
    return run_dir / _TABLET_DIRNAME


def is_expected_arguments(value) -> bool:
    """True only for exactly {"order_id": "A-1", "amount": 42} with strict types.

    Shared by manifest, stored-request and ledger-row validation so 42.0, True and
    extra keys are rejected the same way everywhere. Callers that need independent
    expectations (tests) should keep their own literals.
    """
    return (
        isinstance(value, dict) and set(value) == set(EXPECTED_ARGUMENTS)
        and type(value["order_id"]) is str and value["order_id"] == EXPECTED_ARGUMENTS["order_id"]
        and type(value["amount"]) is int and value["amount"] == EXPECTED_ARGUMENTS["amount"]
    )


def is_expected_confirmed_result(value) -> bool:
    """Strict check of a saved result: exact keys, str/int/str types and values."""
    return (
        isinstance(value, dict) and set(value) == set(EXPECTED_CONFIRMED_RESULT)
        and type(value["status"]) is str and value["status"] == EXPECTED_CONFIRMED_RESULT["status"]
        and is_expected_arguments({key: value[key] for key in EXPECTED_ARGUMENTS})
    )


def record_error_code(record_verdict: str) -> str:
    """Error code for a non-matching ledger verdict: absent -> record_absent, etc."""
    return f"record_{record_verdict}"

# One entry per error code: (message, HTTP status, State phase or None).
# unknown_run and invalid_request have no phase: they never come with a State.
ERROR_DEFINITIONS = {
    "record_absent": ("No committed payment matches the original request; outcome remains unresolved.", 409, PHASE_UNRESOLVED),
    "record_ambiguous": ("More than one payment row exists; the outcome cannot be confirmed and remains unresolved.", 409, PHASE_UNRESOLVED),
    "record_mismatched": ("The only payment row does not match the original request; outcome remains unresolved.", 409, PHASE_UNRESOLVED),
    "record_unreadable": ("The ledger database could not be read; outcome remains unresolved.", 409, PHASE_UNRESOLVED),
    "recovery_conflict": ("A different result is already saved for this call; it was left unchanged.", 409, PHASE_UNRESOLVED),
    "unsupported_history": ("Rumi cannot safely recover this history shape; nothing was repaired.", 409, PHASE_UNSUPPORTED),
    "original_request_missing": ("The original stored tool request could not be found; nothing was recorded.", 409, PHASE_UNSUPPORTED),
    "demo_identity_mismatch": ("The stored history does not match this demo's agent, call or arguments; nothing was recorded.", 409, PHASE_UNSUPPORTED),
    "worker_timeout": ("A worker process timed out; completion is unknown. Inspect the run again.", 502, PHASE_ERROR),
    "worker_failed": ("A worker process failed unexpectedly; completion is unknown. Inspect the run again.", 502, PHASE_ERROR),
    "inspection_failed": ("Fresh inspection did not complete; completion is unknown. Inspect the run again.", 502, PHASE_ERROR),
    "storage_failed": ("Run storage could not be read or written.", 500, PHASE_ERROR),
    "unknown_run": ("Demo run not found.", 404, None),
    "invalid_request": ("Invalid run ID.", 400, None),
}
ERROR_MESSAGES = {code: message for code, (message, _, _) in ERROR_DEFINITIONS.items()}
HTTP_STATUS_BY_ERROR_CODE = {code: status for code, (_, status, _) in ERROR_DEFINITIONS.items()}
PHASE_BY_ERROR_CODE = {code: phase for code, (_, _, phase) in ERROR_DEFINITIONS.items()
                       if phase is not None}


class DemoError(Exception):
    """A refused or failed demo operation, with the HTTP status and (when known) a fresh State."""

    def __init__(self, code: str, message: str | None = None, http_status: int | None = None,
                 state: dict | None = None):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, code)
        self.http_status = http_status or HTTP_STATUS_BY_ERROR_CODE.get(code, 500)
        self.state = state
        super().__init__(f"{code}: {self.message}")
