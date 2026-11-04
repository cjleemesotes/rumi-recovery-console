"""Assertions on a returned State and on a pending run's on-disk evidence."""
from __future__ import annotations

from pathlib import Path

from integration.checks.expectations import (
    AGENT_ID,
    AGENT_TYPE,
    EXPECTED_LEDGER_ROW,
    EXPECTED_MATCHED_VERIFICATION,
    EXPECTED_RECOVERED_RESULT,
    EXPECTED_RECOVERED_RESULT_TEXT,
    EXPECTED_SINGLE_ROW_LEDGER,
    STATE_FIELD_NAMES,
    TOOL_CALL_ID,
    build_expected_request,
)
from integration.checks.results import record_check
from integration.checks.storage import read_history_entries, read_ledger_rows, read_run_manifest

__all__ = [
    "check_pending_evidence_on_disk", "check_pending_state", "check_recovered_state",
    "check_state_has_spec_fields",
]


def check_state_has_spec_fields(label: str, state: object) -> bool:
    has_spec_fields = isinstance(state, dict) and set(state) == STATE_FIELD_NAMES
    return record_check(f"{label}: State has exactly the SPEC fields", has_spec_fields,
                 state if not isinstance(state, dict) else sorted(set(state) ^ STATE_FIELD_NAMES))


def check_pending_state(label: str, state: dict, run_id: str | None = None) -> None:
    check_state_has_spec_fields(label, state)
    record_check(f"{label}: phase pending", state.get("phase") == "pending", state.get("phase"))
    if run_id:
        record_check(f"{label}: run_id", state.get("run_id") == run_id, state.get("run_id"))
    record_check(f"{label}: agent demo.cashier.Cashier/till-1",
          state.get("agent") == {"type": AGENT_TYPE, "id": AGENT_ID}, state.get("agent"))
    reported_request = state.get("request") or {}
    record_check(f"{label}: request is the original call",
          reported_request == build_expected_request(reported_request.get("request_idea_id")) and bool(reported_request.get("request_idea_id")), reported_request)
    record_check(f"{label}: pending_calls == [request]", state.get("pending_calls") == [reported_request],
          state.get("pending_calls"))
    record_check(f"{label}: ledger one A-1/42 row",
          state.get("ledger") == EXPECTED_SINGLE_ROW_LEDGER,
          state.get("ledger"))
    record_check(f"{label}: saved_result null", state.get("saved_result") is None, state.get("saved_result"))
    record_check(f"{label}: counts 1/0/1",
          state.get("counts") == {"records": 1, "saved_results": 0, "pending_calls": 1},
          state.get("counts"))
    record_check(f"{label}: verification matched/fresh/17",
          state.get("verification") == EXPECTED_MATCHED_VERIFICATION, state.get("verification"))
    record_check(f"{label}: error null", state.get("error") is None, state.get("error"))


def check_recovered_state(label: str, state: dict, run_id: str, request_idea_id: str,
                    idea_id: str | None = None) -> None:
    check_state_has_spec_fields(label, state)
    record_check(f"{label}: phase recovered", state.get("phase") == "recovered",
          (state.get("phase"), state.get("error")))
    record_check(f"{label}: run_id", state.get("run_id") == run_id, state.get("run_id"))
    record_check(f"{label}: request preserved", state.get("request") == build_expected_request(request_idea_id),
          state.get("request"))
    record_check(f"{label}: pending_calls empty", state.get("pending_calls") == [], state.get("pending_calls"))
    record_check(f"{label}: ledger still one row",
          state.get("ledger") == EXPECTED_SINGLE_ROW_LEDGER,
          state.get("ledger"))
    saved_result = state.get("saved_result") or {}
    expected_saved_result = {"request_idea_id": request_idea_id, "tool_call_id": TOOL_CALL_ID, "tool_name": "record_payment",
            "content": EXPECTED_RECOVERED_RESULT_TEXT, "result": EXPECTED_RECOVERED_RESULT, "recovered": True}
    record_check(f"{label}: saved_result is the confirmed recovered result",
          {field: saved_result.get(field) for field in expected_saved_result} == expected_saved_result and bool(saved_result.get("idea_id")), saved_result)
    if idea_id:
        record_check(f"{label}: same saved_result.idea_id", saved_result.get("idea_id") == idea_id,
              (saved_result.get("idea_id"), idea_id))
    record_check(f"{label}: counts 1/1/0",
          state.get("counts") == {"records": 1, "saved_results": 1, "pending_calls": 0},
          state.get("counts"))
    record_check(f"{label}: verification matched/fresh/17",
          state.get("verification") == EXPECTED_MATCHED_VERIFICATION, state.get("verification"))
    record_check(f"{label}: error null", state.get("error") is None, state.get("error"))


def check_pending_evidence_on_disk(label: str, storage_root: Path, run_id: str, request_idea_id: str) -> None:
    history_entries = read_history_entries(storage_root, run_id)
    record_check(f"{label}: disk history is [text, tool_request]",
          [entry.get("kind") for entry in history_entries] == ["text", "tool_request"], [entry.get("kind") for entry in history_entries])
    request_entry = next((entry for entry in history_entries if entry.get("kind") == "tool_request"), {})
    record_check(f"{label}: disk request id == API request_idea_id", request_entry.get("id") == request_idea_id,
          (request_entry.get("id"), request_idea_id))
    ledger_rows = read_ledger_rows(storage_root, run_id)
    record_check(f"{label}: disk ledger one row", ledger_rows == [EXPECTED_LEDGER_ROW], ledger_rows)
    try:
        manifest = read_run_manifest(storage_root, run_id)
    except Exception as exc:  # noqa: BLE001
        manifest = {"error": repr(exc)}
    record_check(f"{label}: run.json retains request_idea_id/ids",
          manifest.get("request_idea_id") == request_idea_id and manifest.get("run_id") == run_id
          and manifest.get("agent_type") == AGENT_TYPE and manifest.get("agent_id") == AGENT_ID,
          manifest)
