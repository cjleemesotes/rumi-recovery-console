"""Refusal and validation scenarios: nothing may be guessed into success.

Ledger evidence refusals (absent / duplicate / mismatched / unreadable), unsupported
history, false-success edges (recovered flag, contradictory run.json, worker exit),
and invalid HTTP bodies, ids, methods and routes.
"""
from __future__ import annotations

import json

from rumi import TextIdea

from integration.checks.assertions import check_state_has_spec_fields
from integration.checks.expectations import (
    EXPECTED_LEDGER_ROW,
    EXPECTED_RECOVERED_RESULT,
    MAX_REQUEST_BODY_BYTES,
    UNUSED_HEX_ID,
    build_expected_request,
)
from integration.checks.http_client import send_chunked_post, send_http_request
from integration.checks.processes import LauncherProcess
from integration.checks.results import record_check, record_check_or_abort
from integration.checks.storage import (
    execute_ledger_sql,
    ledger_path,
    open_history_tablet,
    read_history_file_bytes,
    read_ledger_rows,
    run_manifest_path,
    runs_directory,
)

__all__ = ["check_evidence_refusals", "check_false_success_edges", "check_invalid_requests"]


def _create_pending_run(launcher: LauncherProcess, label: str) -> tuple[str, str]:
    status, _, state = send_http_request(launcher.port, "POST", "/api/runs", {})
    record_check_or_abort(f"{label}: POST /api/runs -> 201", status == 201 and state.get("phase") == "pending",
            (status, state))
    return state["run_id"], state["request"]["request_idea_id"]


def _check_recovery_refused(launcher: LauncherProcess, label: str, run_id: str, request_idea_id: str, expected_phase: str, expected_error_code: str,
             expected_ledger: dict | None, expected_record_count) -> None:
    storage_root, port = launcher.storage_root, launcher.port
    history_before = read_history_file_bytes(storage_root, run_id)
    status, _, state = send_http_request(port, "GET", f"/api/runs/{run_id}")
    record_check(f"{label}: GET -> 200", status == 200, (status, state))
    check_state_has_spec_fields(f"{label}: GET", state)
    record_check(f"{label}: GET phase {expected_phase} / {expected_error_code}", state.get("phase") == expected_phase
          and (state.get("error") or {}).get("code") == expected_error_code, (state.get("phase"), state.get("error")))
    status, _, state = send_http_request(port, "POST", f"/api/runs/{run_id}/recover", {})
    record_check(f"{label}: recover -> 409", status == 409, (status, state))
    check_state_has_spec_fields(f"{label}: recover", state)
    error = state.get("error") or {}
    record_check(f"{label}: recover phase {expected_phase} / {expected_error_code}", state.get("phase") == expected_phase
          and error.get("code") == expected_error_code and bool(error.get("message")), (state.get("phase"), error))
    record_check(f"{label}: no saved result", state.get("saved_result") is None
          and (state.get("counts") or {}).get("saved_results") == 0, state.get("saved_result"))
    if expected_phase == "unresolved":
        record_check(f"{label}: request + pending preserved",
              state.get("request") == build_expected_request(request_idea_id)
              and state.get("pending_calls") == [build_expected_request(request_idea_id)]
              and (state.get("counts") or {}).get("pending_calls") == 1, state)
        record_check(f"{label}: ledger evidence {expected_ledger}", state.get("ledger") == expected_ledger
              and (state.get("counts") or {}).get("records") == expected_record_count,
              (state.get("ledger"), state.get("counts")))
    record_check(f"{label}: no history write", read_history_file_bytes(storage_root, run_id) == history_before)
    if expected_phase == "unsupported":
        record_check(f"{label}: error.reason is the Rumi reason",
              error.get("reason") == "history_continues", error)


def check_evidence_refusals(launcher: LauncherProcess) -> None:
    storage_root = launcher.storage_root
    run_id, request_idea_id = _create_pending_run(launcher, "absent")
    execute_ledger_sql(storage_root, run_id, "DELETE FROM payments")
    _check_recovery_refused(launcher, "absent", run_id, request_idea_id, "unresolved", "record_absent",
             {"rows": [], "count": 0}, 0)

    run_id, request_idea_id = _create_pending_run(launcher, "duplicate")
    execute_ledger_sql(storage_root, run_id, "INSERT INTO payments (order_id, amount) VALUES (?, ?)", EXPECTED_LEDGER_ROW)
    _check_recovery_refused(launcher, "duplicate", run_id, request_idea_id, "unresolved", "record_ambiguous",
             {"rows": [{"order_id": "A-1", "amount": 42}, {"order_id": "A-1", "amount": 42}],
              "count": 2}, 2)
    record_check("duplicate: refusal added no ledger row", len(read_ledger_rows(storage_root, run_id)) == 2)

    run_id, request_idea_id = _create_pending_run(launcher, "mismatch")
    execute_ledger_sql(storage_root, run_id, "UPDATE payments SET amount = 43")
    _check_recovery_refused(launcher, "mismatch", run_id, request_idea_id, "unresolved", "record_mismatched",
             {"rows": [{"order_id": "A-1", "amount": 43}], "count": 1}, 1)

    run_id, request_idea_id = _create_pending_run(launcher, "unreadable")
    ledger_path(storage_root, run_id).write_bytes(b"this is not a sqlite database" * 64)
    _check_recovery_refused(launcher, "unreadable", run_id, request_idea_id, "unresolved", "record_unreadable",
             {"rows": None, "count": None}, None)

    run_id, request_idea_id = _create_pending_run(launcher, "unsupported")
    history_tablet = open_history_tablet(storage_root, run_id)
    later_idea = TextIdea(role="user", content="a later idea after the unfinished request")
    history_tablet.set(f"history/{later_idea.id}", later_idea.to_dict())
    _check_recovery_refused(launcher, "unsupported", run_id, request_idea_id, "unsupported", "unsupported_history", None, None)
    record_check("unsupported: ledger untouched", read_ledger_rows(storage_root, run_id) == [EXPECTED_LEDGER_ROW])


def _check_no_false_success(launcher: LauncherProcess, label: str, run_id: str) -> None:
    """GET must not claim pending/recovered success; recover must not succeed or write."""
    storage_root, port = launcher.storage_root, launcher.port
    history_before = read_history_file_bytes(storage_root, run_id)
    status, _, state = send_http_request(port, "GET", f"/api/runs/{run_id}")
    claims_no_success = isinstance(state, dict) and state.get("phase") not in ("pending", "recovered") \
        and bool(state.get("error"))
    record_check(f"{label}: GET does not claim success (phase/error)", claims_no_success,
          (status, state.get("phase") if isinstance(state, dict) else state,
           state.get("error") if isinstance(state, dict) else None))
    status, _, state = send_http_request(port, "POST", f"/api/runs/{run_id}/recover", {})
    phase = state.get("phase") if isinstance(state, dict) else None
    record_check(f"{label}: recover refused (non-2xx, not recovered)",
          status >= 400 and phase != "recovered",
          (status, phase, state.get("error") if isinstance(state, dict) else state))
    record_check(f"{label}: no history write", read_history_file_bytes(storage_root, run_id) == history_before)


def check_false_success_edges(launcher: LauncherProcess) -> None:
    """Targeted probes for the coordinator's three false-green edges."""
    storage_root, port = launcher.storage_root, launcher.port

    # A. metadata.recovered must be literally True.
    run_id, _ = _create_pending_run(launcher, "edge recovered-flag")
    recovered_run_id = run_id  # reused by the worker-exit probe on a recovered run (C)
    status, _, state = send_http_request(port, "POST", f"/api/runs/{run_id}/recover", {})
    record_check_or_abort("edge recovered-flag: baseline recover -> 200", status == 200
            and state.get("phase") == "recovered", (status, state.get("phase"), state.get("error")))
    history_tablet = open_history_tablet(storage_root, run_id)
    result_history_key = next(history_key for history_key in history_tablet.list_keys("history/") if (history_tablet.get(history_key) or {}).get("kind") == "tool_result")
    original_result_entry = history_tablet.get(result_history_key)
    for invalid_metadata in ({"recovered": 1}, {"recovered": "true"}, {}):
        history_tablet.set(result_history_key, {**original_result_entry, "metadata": invalid_metadata})
        _check_no_false_success(launcher, f"edge recovered-flag metadata={invalid_metadata}", run_id)
    history_tablet.set(result_history_key, original_result_entry)
    status, _, state = send_http_request(port, "GET", f"/api/runs/{run_id}")
    record_check("edge recovered-flag: restored literal True -> recovered again",
          status == 200 and state.get("phase") == "recovered", (status, state.get("phase")))

    # B. Contradictory manifest identity (pending and recovered runs).
    manifest_path = run_manifest_path(storage_root, run_id)
    recovered_run_manifest_bytes = manifest_path.read_bytes()
    manifest_fields = json.loads(recovered_run_manifest_bytes)
    manifest_path.write_text(json.dumps({**manifest_fields, "tool_call_id": "call_other"}), "utf-8")
    _check_no_false_success(launcher, "edge manifest(recovered run) tool_call_id=call_other", run_id)
    manifest_path.write_bytes(recovered_run_manifest_bytes)

    run_id, _ = _create_pending_run(launcher, "edge manifest")
    manifest_path = run_manifest_path(storage_root, run_id)
    pristine_manifest_bytes = manifest_path.read_bytes()
    manifest_fields = json.loads(pristine_manifest_bytes)
    for field, value in (("tool_call_id", "call_other"), ("tool_name", "refund"),
                         ("arguments", {"order_id": "A-1", "amount": 43}),
                         ("arguments", {"order_id": "A-1", "amount": 42.0}),
                         ("version", 2), ("agent_id", "till-2"),
                         ("request_idea_id", UNUSED_HEX_ID)):
        manifest_path.write_text(json.dumps({**manifest_fields, field: value}), "utf-8")
        _check_no_false_success(launcher, f"edge manifest {field}={value!r}", run_id)
        manifest_path.write_bytes(pristine_manifest_bytes)
    record_check("edge manifest: ledger untouched by refused recovers", read_ledger_rows(storage_root, run_id) == [EXPECTED_LEDGER_ROW])

    # C. Recorded worker exit unknown/wrong (UI would claim 17).
    for value in (None, 0, 1, "17"):
        manifest_path.write_text(json.dumps({**manifest_fields, "worker_exit_code": value}), "utf-8")
        _check_no_false_success(launcher, f"edge exit(pending run) worker_exit_code={value!r}", run_id)
        manifest_path.write_bytes(pristine_manifest_bytes)
    status, _, state = send_http_request(port, "GET", f"/api/runs/{run_id}")
    record_check("edge manifest/exit: restored manifest -> pending again",
          status == 200 and state.get("phase") == "pending", (status, state.get("phase")))
    # recovered run with a wrong exit must not show recovered either
    exit_probe_manifest_path = run_manifest_path(storage_root, recovered_run_id)
    exit_probe_manifest_bytes = exit_probe_manifest_path.read_bytes()
    exit_probe_manifest_path.write_text(json.dumps({**json.loads(exit_probe_manifest_bytes), "worker_exit_code": 0}), "utf-8")
    _check_no_false_success(launcher, "edge exit(recovered run) worker_exit_code=0", recovered_run_id)
    exit_probe_manifest_path.write_bytes(exit_probe_manifest_bytes)


def check_invalid_requests(launcher: LauncherProcess, main_run: dict) -> None:
    storage_root, port = launcher.storage_root, launcher.port
    main_run_id = main_run["run_id"]
    run_count_before = len(list(runs_directory(storage_root).iterdir()))
    history_before = read_history_file_bytes(storage_root, main_run_id)

    for label, path in (("non-hex id", "/api/runs/XYZ"), ("uppercase id", "/api/runs/" + "A" * 32),
                        ("short id", "/api/runs/" + "a" * 31)):
        status, _, response_body = send_http_request(port, "GET", path)
        record_check(f"GET {label} -> 400 invalid_request", status == 400
              and isinstance(response_body, dict) and (response_body.get("error") or {}).get("code") == "invalid_request",
              (status, response_body))
    unknown_run_id = UNUSED_HEX_ID
    status, _, response_body = send_http_request(port, "GET", f"/api/runs/{unknown_run_id}")
    record_check("GET unknown run -> 404 unknown_run envelope",
          status == 404 and response_body == {"error": {"code": "unknown_run", "message": "Demo run not found."}}, (status, response_body))
    status, _, response_body = send_http_request(port, "POST", f"/api/runs/{unknown_run_id}/recover", {})
    record_check("recover unknown run -> 404", status == 404, (status, response_body))

    for label, request_kwargs in (
        ("result field", {"body": {"result": EXPECTED_RECOVERED_RESULT}}),
        ("outcome field", {"body": {"outcome": "recorded"}}),
        ("path field", {"body": {"path": "C:/"}}),
        ("array body", {"raw": b"[]"}),
        ("malformed JSON", {"raw": b"{"}),
        ("non-UTF-8", {"raw": b"\xff\xfe{}"}),
    ):
        status, _, response_body = send_http_request(port, "POST", f"/api/runs/{main_run_id}/recover", **request_kwargs)
        record_check(f"recover with {label} -> 400 invalid_request", status == 400
              and isinstance(response_body, dict) and (response_body.get("error") or {}).get("code") == "invalid_request",
              (status, response_body))
        status, _, response_body = send_http_request(port, "POST", "/api/runs", **request_kwargs)
        record_check(f"POST /api/runs with {label} -> 400", status == 400, (status, response_body))
    status, _, _ = send_http_request(port, "POST", "/api/runs", raw=b"{" + b" " * MAX_REQUEST_BODY_BYTES + b"}")
    record_check("POST body > 4096 bytes -> 413", status == 413, status)
    status = send_chunked_post(port, "/api/runs")
    record_check("transfer-encoded POST rejected (4xx)", 400 <= status < 500, status)
    record_check("rejected POSTs created no run", len(list(runs_directory(storage_root).iterdir())) == run_count_before)
    record_check("rejected recovers wrote no history", read_history_file_bytes(storage_root, main_run_id) == history_before)

    status, response_headers, _ = send_http_request(port, "GET", "/api/runs")
    record_check("GET /api/runs -> 405 Allow: POST", status == 405 and "POST" in response_headers.get("allow", ""), (status, response_headers))
    status, response_headers, _ = send_http_request(port, "PUT", "/api/state", {})
    record_check("PUT /api/state -> 405 with Allow", status == 405 and "GET" in response_headers.get("allow", ""), (status, response_headers))
    status, response_headers, _ = send_http_request(port, "GET", f"/api/runs/{main_run_id}/recover")
    record_check("GET recover -> 405 Allow: POST", status == 405 and "POST" in response_headers.get("allow", ""), (status, response_headers))
    for path in ("/api/state/", "/api/nope", "/index.html/", "/app.js/"):
        status, _, _ = send_http_request(port, "GET", path)
        record_check(f"GET {path} -> 404", status == 404, status)
