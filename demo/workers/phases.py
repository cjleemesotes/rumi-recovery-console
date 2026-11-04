"""The three worker phases (crash, inspect, recover) and run-directory validation.

Each phase runs in a fresh interpreter that rebuilds the Cashier from storage.
The model is mocked; nothing touches the network.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from rumi import RecoveryConflictError, ToolCallNotFoundError, UnsupportedRecoveryError

from demo.cashier import open_agent
from demo.runtime.contract import (
    CALL_ID, EXPECTED_ARGUMENTS, STORAGE_ROOT_ENV, TOOL_NAME, WORKER_CRASH, WORKER_INSPECT,
    WORKER_RECOVER, is_valid_run_id, ledger_path, manifest_path, runs_dir, tablet_dir,
    record_error_code,
)
from demo.workers.history import find_original_request, results_after_request
from demo.workers.ledger import classify_demo_payment_evidence, read_payments_ledger

__all__ = [
    "InvalidRunSetupError", "PHASE_HANDLERS", "resolve_validated_run_directory",
    "phase_crash", "phase_inspect", "phase_recover",
]

MOCKED_MODEL_CALL_TARGET = "rumi.heart.openrouter.OpenRouterHeart.call"


class InvalidRunSetupError(Exception):
    """The worker was started with a missing storage root or an invalid run directory."""


def resolve_validated_run_directory(raw_run_dir: str) -> Path:
    storage = os.environ.get(STORAGE_ROOT_ENV)
    if not storage:
        raise InvalidRunSetupError(f"{STORAGE_ROOT_ENV} is not set")
    run_dir = Path(raw_run_dir).resolve()
    if run_dir.parent != runs_dir(storage) or not is_valid_run_id(run_dir.name) or not run_dir.is_dir():
        raise InvalidRunSetupError("run directory is not a valid run under the storage root")
    return run_dir


def _mock_tool_request_response() -> dict:
    return {"choices": [{"message": {"content": None, "tool_calls": [{
        "id": CALL_ID, "type": "function",
        "function": {"name": TOOL_NAME, "arguments": json.dumps(EXPECTED_ARGUMENTS)},
    }]}}]}


def _read_run_manifest(run_dir: Path) -> dict:
    try:
        data = json.loads(manifest_path(run_dir).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def phase_crash(run_dir: Path) -> dict:
    agent = open_agent(tablet_dir(run_dir))
    with patch(MOCKED_MODEL_CALL_TARGET, return_value=_mock_tool_request_response()):
        agent.whirl("Charge order A-1 42 dollars.")
    return {"error": "the tool returned; this worker should have died inside it"}


def phase_inspect(run_dir: Path) -> dict:
    """Read-only report: history, pending calls, original call, its results, ledger evidence."""
    agent = open_agent(tablet_dir(run_dir))
    retained_request_idea_id = _read_run_manifest(run_dir).get("request_idea_id")
    history = {"supported": True, "reason": None, "calls": None}
    pending = None
    try:
        pending = agent.pending_tool_calls()
    except UnsupportedRecoveryError as exc:
        history = {"supported": False, "reason": exc.reason, "calls": exc.calls}
    original_call, request_problem, request_index = find_original_request(
        agent, retained_request_idea_id)
    original_call_results = results_after_request(agent, request_index) if original_call else []
    ledger = read_payments_ledger(ledger_path(run_dir))
    return {"history": history, "pending": pending, "request": original_call,
            "request_problem": request_problem, "saved_results": original_call_results,
            "ledger": ledger,
            "record": classify_demo_payment_evidence(ledger) if original_call else "not_checked"}


def phase_recover(run_dir: Path) -> dict:
    """Record the ledger-confirmed result through Rumi, only if exactly one row matches.

    Reports only ``outcome`` (and ``idea_id`` when saved): the parent never trusts this
    report as proof and re-derives every detail from a fresh inspect child.
    """
    agent = open_agent(tablet_dir(run_dir))
    retained_request_idea_id = _read_run_manifest(run_dir).get("request_idea_id")
    try:
        agent.pending_tool_calls()
    except UnsupportedRecoveryError:
        return {"outcome": "unsupported_history"}
    original_call, request_problem, _ = find_original_request(agent, retained_request_idea_id)
    if original_call is None:
        return {"outcome": request_problem}
    ledger = read_payments_ledger(ledger_path(run_dir))
    record_verdict = classify_demo_payment_evidence(ledger)
    if record_verdict != "matched":
        return {"outcome": record_error_code(record_verdict)}
    row = ledger["rows"][0]
    confirmed = {"order_id": row["order_id"], "amount": row["amount"], "status": "recorded"}
    try:
        saved = agent.record_recovered_result(
            original_call["request_idea_id"], original_call["tool_call_id"], confirmed)
    except RecoveryConflictError:
        return {"outcome": "recovery_conflict"}
    except UnsupportedRecoveryError:
        return {"outcome": "unsupported_history"}
    except ToolCallNotFoundError:
        return {"outcome": "original_request_missing"}
    return {"outcome": "saved", "idea_id": saved.id}


PHASE_HANDLERS = {WORKER_CRASH: phase_crash, WORKER_INSPECT: phase_inspect,
                  WORKER_RECOVER: phase_recover}
