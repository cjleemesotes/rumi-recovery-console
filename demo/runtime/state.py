"""Build the State snapshot dicts returned by the runner (pure functions, no I/O)."""
from __future__ import annotations

from demo.runtime.contract import (
    AGENT_ID, AGENT_TYPE, CALL_ID, CRASH_EXIT_CODE, ERROR_MESSAGES, EXPECTED_ARGUMENTS,
    HTTP_STATUS_BY_ERROR_CODE, PHASE_BY_ERROR_CODE, PHASE_ERROR,
    PHASE_IDLE, PHASE_PENDING, PHASE_RECOVERED, PHASE_UNRESOLVED, PHASE_UNSUPPORTED,
    SCHEMA_VERSION, TOOL_NAME, DemoError, is_expected_confirmed_result, record_error_code,
)

__all__ = [
    "empty_state", "error_payload", "unavailable_state", "state_from_inspection",
    "state_with_error", "raise_demo_error_from_state",
]


def empty_state() -> dict:
    """The idle State: no run yet, counters 0/0/0."""
    return {
        "schema_version": SCHEMA_VERSION, "demo": True, "phase": PHASE_IDLE, "run_id": None,
        "agent": None, "request": None, "pending_calls": [],
        "ledger": {"rows": [], "count": 0}, "saved_result": None,
        "counts": {"records": 0, "saved_results": 0, "pending_calls": 0},
        "verification": {"record": "not_checked", "fresh_inspection": False,
                         "worker_exit_code": None},
        "error": None,
    }


def error_payload(code: str, reason=None, message: str | None = None) -> dict:
    error_dict = {"code": code, "message": message or ERROR_MESSAGES[code]}
    if reason is not None:
        error_dict["reason"] = reason
    return error_dict


def unavailable_state(manifest: dict, code: str, detail: str = "") -> dict:
    """State when a fresh inspection is not available: unknowns are null."""
    request = None
    if manifest.get("request_idea_id"):
        request = {"request_idea_id": manifest["request_idea_id"], "tool_call_id": CALL_ID,
                   "tool_name": TOOL_NAME, "arguments": dict(EXPECTED_ARGUMENTS)}
    message = ERROR_MESSAGES[code] + (f" ({detail})" if detail else "")
    state = empty_state()
    state.update({
        "phase": PHASE_BY_ERROR_CODE[code], "run_id": manifest["run_id"],
        "agent": {"type": AGENT_TYPE, "id": AGENT_ID}, "request": request,
        "pending_calls": None, "ledger": {"rows": None, "count": None},
        "counts": {"records": None, "saved_results": None, "pending_calls": None},
        "verification": {"record": "not_checked", "fresh_inspection": False,
                         "worker_exit_code": manifest.get("worker_exit_code")},
        "error": error_payload(code, message=message),
    })
    return state


def state_from_inspection(manifest: dict, inspection: dict) -> dict:
    """Turn one worker inspection report plus the run manifest into a State."""
    request = inspection.get("request")
    request_problem = inspection.get("request_problem")
    history = inspection.get("history") or {}
    ledger = inspection.get("ledger") or {"rows": None, "count": None}
    record = inspection.get("record", "not_checked")
    original_call_results = inspection.get("saved_results") or []
    pending = inspection.get("pending")
    error = None
    saved = None

    if history.get("supported") is False:
        pending = history.get("calls")
        error = error_payload("unsupported_history", reason=history.get("reason"))
    elif request_problem:
        error = error_payload(request_problem)
    elif len(original_call_results) > 1:
        error = error_payload("unsupported_history", reason="duplicate_results")
    if original_call_results:
        saved = original_call_results[0]

    phase = None
    if error:
        phase = PHASE_BY_ERROR_CODE[error["code"]]
    elif saved is not None:
        is_expected_result = (saved.get("recovered") is True
                              and is_expected_confirmed_result(saved.get("result")))
        if not is_expected_result:
            error = error_payload("recovery_conflict")
            phase = PHASE_UNRESOLVED
        elif pending != []:
            error = error_payload("unsupported_history", reason="pending_after_result")
            phase = PHASE_UNSUPPORTED
        elif record != "matched":
            error = error_payload(record_error_code(record))
            phase = PHASE_UNRESOLVED
        else:
            phase = PHASE_RECOVERED
    elif pending and request and pending == [request]:
        if record == "matched":
            phase = PHASE_PENDING
        else:
            error = error_payload(record_error_code(record))
            phase = PHASE_UNRESOLVED
    else:
        error = error_payload("demo_identity_mismatch")
        phase = PHASE_UNSUPPORTED

    if (phase in (PHASE_PENDING, PHASE_RECOVERED)
            and manifest.get("worker_exit_code") != CRASH_EXIT_CODE):
        error = error_payload("worker_failed", message=(
            "The crash worker's exit code 17 was not confirmed for this run; "
            "this is not a verified demo state."))
        phase = PHASE_ERROR

    counts = {
        "records": ledger.get("count"),
        "saved_results": len(original_call_results) if (request or not request_problem) else None,
        "pending_calls": None if pending is None else len(pending),
    }
    return {
        "schema_version": SCHEMA_VERSION, "demo": True, "phase": phase,
        "run_id": manifest["run_id"], "agent": {"type": AGENT_TYPE, "id": AGENT_ID},
        "request": request, "pending_calls": pending,
        "ledger": {"rows": ledger.get("rows"), "count": ledger.get("count")},
        "saved_result": saved, "counts": counts,
        "verification": {"record": record, "fresh_inspection": True,
                         "worker_exit_code": manifest.get("worker_exit_code")},
        "error": error,
    }


def state_with_error(state: dict, code: str, detail: str) -> dict:
    """Copy of ``state`` carrying a worker/inspection error and its phase."""
    message = ERROR_MESSAGES[code] + (f" ({detail})" if detail else "")
    updated = dict(state)
    updated["error"] = error_payload(code, message=message)
    updated["phase"] = PHASE_BY_ERROR_CODE[code]
    return updated


def raise_demo_error_from_state(state: dict):
    """Raise the DemoError matching ``state['error']``, carrying that State."""
    error_dict = state["error"]
    raise DemoError(error_dict["code"], error_dict["message"],
                    HTTP_STATUS_BY_ERROR_CODE.get(error_dict["code"], 409), state)
