"""The four public runner operations: start, current, inspect, recover.

The parent never builds a World/Cashier or runs a tool. It creates storage,
launches fresh worker children and assembles State from what they report.

Flow, each step a separate fresh child process (see ``demo.workers.phases``):
  start_run    crash (exits 17 inside the tool after the SQLite commit) -> inspect
  recover_run  inspect (pins the original request id in run.json) -> recover
               (child checks the ledger and records via Rumi's API) -> inspect again
Recovery succeeds only if that final, independent inspect child finds the same
recovered result, zero pending calls and still exactly one matching ledger row.
The tool and the model are never re-run during inspection or recovery.
"""
from __future__ import annotations

import json
import uuid

from demo.runtime.children import (
    ChildProcessFailure, run_child_for_json, run_worker_phase, stderr_tail,
)
from demo.runtime.contract import (
    AGENT_ID, AGENT_TYPE, CALL_ID, CRASH_EXIT_CODE, EXPECTED_ARGUMENTS, PHASE_BY_ERROR_CODE,
    PHASE_ERROR, PHASE_PENDING, PHASE_RECOVERED, PHASE_UNSUPPORTED, TOOL_NAME, WORKER_CRASH,
    WORKER_INSPECT, WORKER_RECOVER, DemoError, active_run_path, ledger_path, manifest_path,
    tablet_dir,
)
from demo.runtime.state import (
    empty_state, error_payload, raise_demo_error_from_state, state_from_inspection,
    state_with_error, unavailable_state,
)
from demo.runtime.storage import (
    create_payments_ledger, load_manifest, run_directory, save_manifest_update,
    write_json_atomically,
)

__all__ = ["start_run", "current_state", "inspect_run", "recover_run"]


def _fresh_inspection_state(storage_root, manifest: dict) -> dict:
    """Run a fresh inspect child and build State; raises DemoError(state=...) on failure."""
    run_dir = run_directory(storage_root, manifest["run_id"])
    try:
        inspection = run_child_for_json(storage_root, run_dir, WORKER_INSPECT, "inspection_failed")
    except ChildProcessFailure as exc:
        raise DemoError(exc.code, state=unavailable_state(manifest, exc.code, exc.detail)) from exc
    return state_from_inspection(manifest, inspection)


def start_run(storage_root) -> dict:
    """Allocate a new isolated run, crash the worker mid-tool, and return the pending State."""
    run_id = uuid.uuid4().hex
    run_dir = run_directory(storage_root, run_id)
    try:
        tablet_dir(run_dir).mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise DemoError("storage_failed", f"Could not create the run directory: {exc}") from exc
    create_payments_ledger(ledger_path(run_dir))
    manifest = {
        "version": 1, "run_id": run_id, "agent_type": AGENT_TYPE, "agent_id": AGENT_ID,
        "tool_call_id": CALL_ID, "tool_name": TOOL_NAME, "arguments": dict(EXPECTED_ARGUMENTS),
        "worker_exit_code": None, "request_idea_id": None,
    }
    write_json_atomically(manifest_path(run_dir), manifest)
    write_json_atomically(active_run_path(storage_root), {"run_id": run_id})

    try:
        completed_process = run_worker_phase(storage_root, run_dir, WORKER_CRASH)
    except ChildProcessFailure as exc:
        raise DemoError(exc.code, state=unavailable_state(manifest, exc.code, exc.detail)) from exc
    if completed_process.returncode != CRASH_EXIT_CODE:
        detail = (f"crash worker exited {completed_process.returncode}, "
                  f"expected {CRASH_EXIT_CODE}: {stderr_tail(completed_process)}")
        raise DemoError("worker_failed", state=unavailable_state(manifest, "worker_failed", detail))
    manifest = save_manifest_update(storage_root, manifest, worker_exit_code=completed_process.returncode)

    state = _fresh_inspection_state(storage_root, manifest)
    if state["request"]:
        save_manifest_update(
            storage_root, manifest, request_idea_id=state["request"]["request_idea_id"])
    if state["phase"] != PHASE_PENDING:
        raise_demo_error_from_state(state)
    return state


def inspect_run(storage_root, run_id: str) -> dict:
    """Freshly inspect a run in a new child process."""
    manifest = load_manifest(storage_root, run_id)
    return _fresh_inspection_state(storage_root, manifest)


def current_state(storage_root) -> dict:
    """State of the active run, or the idle State when none exists."""
    path = active_run_path(storage_root)
    if not path.is_file():
        return empty_state()
    try:
        run_id = json.loads(path.read_text(encoding="utf-8")).get("run_id")
    except (OSError, ValueError, AttributeError) as exc:
        raise DemoError("storage_failed", f"Could not read active.json: {exc}") from exc
    return inspect_run(storage_root, run_id)


def recover_run(storage_root, run_id: str) -> dict:
    """Verify the ledger against the stored request, record the result, prove it independently."""
    manifest = load_manifest(storage_root, run_id)
    run_dir = run_directory(storage_root, run_id)

    state_before_recovery = _fresh_inspection_state(storage_root, manifest)
    request = state_before_recovery["request"]
    if request is None or state_before_recovery["phase"] in (PHASE_UNSUPPORTED, PHASE_ERROR):
        raise_demo_error_from_state(state_before_recovery)
    if manifest.get("request_idea_id") is None:
        manifest = save_manifest_update(
            storage_root, manifest, request_idea_id=request["request_idea_id"])
    elif manifest["request_idea_id"] != request["request_idea_id"]:
        raise_demo_error_from_state(
            state_from_inspection(manifest, {"request_problem": "demo_identity_mismatch"}))

    try:
        recover_report = run_child_for_json(storage_root, run_dir, WORKER_RECOVER, "worker_failed")
    except ChildProcessFailure as exc:
        # A timeout or crash may have happened after the save: re-inspect, never assume.
        try:
            state = _fresh_inspection_state(storage_root, manifest)
        except DemoError as inner:
            raise DemoError(exc.code, state=inner.state
                            or unavailable_state(manifest, exc.code, exc.detail)) from exc
        raise DemoError(exc.code, state=state_with_error(state, exc.code, exc.detail)) from exc

    state_after_recovery = _fresh_inspection_state(storage_root, manifest)
    if recover_report.get("outcome") == "saved" and state_after_recovery["phase"] == PHASE_RECOVERED:
        saved = state_after_recovery["saved_result"]
        if saved and saved["idea_id"] == recover_report.get("idea_id"):
            return state_after_recovery
        raise DemoError("inspection_failed", state=state_with_error(
            state_after_recovery, "inspection_failed",
            "saved result id differs from the inspected result"))
    if recover_report.get("outcome") == "saved":
        error_dict = state_after_recovery["error"] or error_payload("inspection_failed")
        raise DemoError("inspection_failed", state=state_with_error(
            state_after_recovery, "inspection_failed",
            f"post-save inspection found phase {state_after_recovery['phase']} ({error_dict['code']})"))
    # Refused: fresh inspection already carries the matching error.
    if state_after_recovery["error"]:
        raise_demo_error_from_state(state_after_recovery)
    code = (recover_report.get("outcome")
            if recover_report.get("outcome") in PHASE_BY_ERROR_CODE else "worker_failed")
    raise DemoError(code, state=state_with_error(state_after_recovery, code, ""))
