"""Happy-path, restart and isolation scenarios.

Startup/static/idle, exclusive bind, crash -> inspect -> recover -> repeat -> refresh,
server restart persistence, new-run isolation, and the preserved Rumi checkout.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from integration.checks.assertions import (
    check_pending_evidence_on_disk,
    check_pending_state,
    check_recovered_state,
    check_state_has_spec_fields,
)
from integration.checks.expectations import (
    EXPECTED_LEDGER_ROW,
    EXPECTED_RECOVERED_RESULT_TEXT,
    RUN_ID_PATTERN,
    TOOL_CALL_ID,
)
from integration.checks.http_client import send_http_request
from integration.checks.processes import LAUNCHER_START_TIMEOUT_SECONDS, LauncherProcess
from integration.checks.results import record_check, record_check_or_abort
from integration.checks.storage import (
    ledger_path,
    read_history_entries,
    read_history_file_bytes,
    read_ledger_rows,
    run_directory,
)
from integration.workspace import LOOPBACK_HOST, RUMI_CHECKOUT_DIR

__all__ = [
    "RumiCheckoutSnapshot", "capture_rumi_checkout_snapshot",
    "check_bind_exclusivity", "check_crash_inspect_recover_flow", "check_new_run_isolation",
    "check_restart_preserves_recovery", "check_rumi_checkout_preserved",
    "check_static_assets_and_idle_state",
]


def check_static_assets_and_idle_state(port: int) -> None:
    status, response_headers, state = send_http_request(port, "GET", "/api/state")
    record_check("GET /api/state 200 on empty storage", status == 200, status)
    check_state_has_spec_fields("idle", state)
    if isinstance(state, dict):
        record_check("idle: phase/counts/verification", state.get("phase") == "idle"
              and state.get("run_id") is None
              and state.get("counts") == {"records": 0, "saved_results": 0, "pending_calls": 0}
              and state.get("ledger") == {"rows": [], "count": 0}
              and state.get("verification") == {"record": "not_checked", "fresh_inspection": False,
                                                "worker_exit_code": None}, state)
    record_check("JSON Cache-Control no-store", "no-store" in response_headers.get("cache-control", ""), response_headers)
    record_check("JSON UTF-8 content-type", "application/json" in response_headers.get("content-type", "")
          and "utf-8" in response_headers.get("content-type", "").lower(), response_headers.get("content-type"))
    for path, expected_content_type in (("/", "text/html"), ("/app.js", "javascript"), ("/styles.css", "text/css")):
        status, response_headers, _ = send_http_request(port, "GET", path)
        record_check(f"static {path} 200 {expected_content_type}", status == 200 and expected_content_type in response_headers.get("content-type", ""),
              (status, response_headers.get("content-type")))
        record_check(f"static {path} no-store", "no-store" in response_headers.get("cache-control", ""), response_headers)
    status, _, _ = send_http_request(port, "GET", "/?x=1")
    record_check("query string ignored for /", status == 200, status)


def check_bind_exclusivity(storage_root: Path, port: int, log_dir: Path) -> None:
    second_launcher = LauncherProcess(storage_root, port, log_dir, "second-bind")
    second_launcher.start()
    try:
        second_launcher_exit_code = second_launcher.process.wait(LAUNCHER_START_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        second_launcher_exit_code = None
    second_launcher_logs = second_launcher.read_log_tail()
    second_launcher.stop()
    record_check("second launcher on the same port exits nonzero", second_launcher_exit_code not in (None, 0), (second_launcher_exit_code, second_launcher_logs))
    record_check("second launcher names host:port", f"{LOOPBACK_HOST}:{port}" in second_launcher_logs, second_launcher_logs)
    status, _, _ = send_http_request(port, "GET", "/api/state")
    record_check("first server still serving after refused second bind", status == 200, status)


def check_crash_inspect_recover_flow(launcher: LauncherProcess) -> dict:
    storage_root, port = launcher.storage_root, launcher.port
    status, _, state = send_http_request(port, "POST", "/api/runs", {})
    record_check_or_abort("POST /api/runs -> 201", status == 201, (status, state))
    run_id = state.get("run_id") or ""
    record_check_or_abort("run_id is 32 lowercase hex", bool(RUN_ID_PATTERN.match(run_id)), run_id)
    check_pending_state("POST /api/runs", state, run_id)
    request_idea_id = (state.get("request") or {}).get("request_idea_id")
    record_check_or_abort("request_idea_id present", bool(request_idea_id), state.get("request"))
    check_pending_evidence_on_disk("after crash", storage_root, run_id, request_idea_id)

    history_before = read_history_file_bytes(storage_root, run_id)
    status, _, state = send_http_request(port, "GET", f"/api/runs/{run_id}")
    record_check("GET /api/runs/{id} pending -> 200", status == 200, status)
    check_pending_state("GET run (pending)", state, run_id)
    record_check("inspection leaves history byte-identical", read_history_file_bytes(storage_root, run_id) == history_before)
    status, _, state = send_http_request(port, "GET", "/api/state")
    record_check("GET /api/state shows the active pending run", status == 200
          and state.get("run_id") == run_id and state.get("phase") == "pending", (status, state))

    status, _, state = send_http_request(port, "POST", f"/api/runs/{run_id}/recover", {})
    record_check_or_abort("POST recover -> 200", status == 200, (status, state))
    check_recovered_state("recover", state, run_id, request_idea_id)
    idea_id = (state.get("saved_result") or {}).get("idea_id")
    history_entries = read_history_entries(storage_root, run_id)
    record_check("disk history is [text, tool_request, tool_result] (no model/tool replay)",
          [entry.get("kind") for entry in history_entries] == ["text", "tool_request", "tool_result"],
          [entry.get("kind") for entry in history_entries])
    saved_result_entry = history_entries[-1] if history_entries else {}
    record_check("disk result: original call id, recovered metadata, exact content, same idea id",
          saved_result_entry.get("tool_call_id") == TOOL_CALL_ID and saved_result_entry.get("metadata") == {"recovered": True}
          and saved_result_entry.get("content") == EXPECTED_RECOVERED_RESULT_TEXT and saved_result_entry.get("id") == idea_id, saved_result_entry)
    ledger_rows = read_ledger_rows(storage_root, run_id)
    record_check("ledger still exactly one row after recovery", ledger_rows == [EXPECTED_LEDGER_ROW], ledger_rows)

    history_after = read_history_file_bytes(storage_root, run_id)
    status, _, state = send_http_request(port, "POST", f"/api/runs/{run_id}/recover", {})
    record_check("repeat recover -> 200", status == 200, (status, state))
    check_recovered_state("repeat recover", state, run_id, request_idea_id, idea_id)
    status, _, state = send_http_request(port, "POST", f"/api/runs/{run_id}/recover")  # absent body == {}
    record_check("repeat recover with absent body -> 200", status == 200, (status, state))
    check_recovered_state("repeat recover (absent body)", state, run_id, request_idea_id, idea_id)
    record_check("repeat recovery wrote no history", read_history_file_bytes(storage_root, run_id) == history_after)
    record_check("repeat recovery added no ledger row", read_ledger_rows(storage_root, run_id) == [EXPECTED_LEDGER_ROW])

    status, _, state = send_http_request(port, "GET", "/api/state")
    record_check("refresh GET /api/state -> 200", status == 200, status)
    check_recovered_state("refresh", state, run_id, request_idea_id, idea_id)
    return {"run_id": run_id, "request_idea_id": request_idea_id, "idea_id": idea_id}


def check_restart_preserves_recovery(launcher: LauncherProcess, log_dir: Path, main_run: dict) -> LauncherProcess:
    storage_root, port = launcher.storage_root, launcher.port
    history_before = read_history_file_bytes(storage_root, main_run["run_id"])
    launcher.stop()
    restarted_launcher = LauncherProcess(storage_root, port, log_dir, "restarted")
    restarted_launcher.start()
    try:
        record_check_or_abort("server restarts on the same port + storage", restarted_launcher.wait_until_serving(),
                restarted_launcher.read_log_tail())
        status, _, state = send_http_request(port, "GET", "/api/state")
        record_check("after restart GET /api/state -> 200", status == 200, status)
        check_recovered_state("after restart /api/state", state, main_run["run_id"], main_run["request_idea_id"], main_run["idea_id"])
        status, _, state = send_http_request(port, "GET", f"/api/runs/{main_run['run_id']}")
        check_recovered_state("after restart GET run", state, main_run["run_id"], main_run["request_idea_id"], main_run["idea_id"])
        status, _, state = send_http_request(port, "POST", f"/api/runs/{main_run['run_id']}/recover", {})
        record_check("after restart repeat recover -> 200", status == 200, status)
        check_recovered_state("after restart repeat recover", state, main_run["run_id"], main_run["request_idea_id"],
                        main_run["idea_id"])
        record_check("restart + repeat wrote no history", read_history_file_bytes(storage_root, main_run["run_id"]) == history_before)
    except BaseException:
        restarted_launcher.stop()  # not yet handed to the suite, so this scenario owns it
        raise
    return restarted_launcher


def check_new_run_isolation(launcher: LauncherProcess, main_run: dict) -> None:
    storage_root, port = launcher.storage_root, launcher.port
    first_run_id = main_run["run_id"]
    first_run_history_bytes = read_history_file_bytes(storage_root, first_run_id)
    first_run_ledger_bytes = ledger_path(storage_root, first_run_id).read_bytes()
    status, _, state = send_http_request(port, "POST", "/api/runs", {})
    record_check("second POST /api/runs -> 201", status == 201, (status, state))
    second_run_id = state.get("run_id")
    record_check("new run has a different id/directory", second_run_id and second_run_id != first_run_id
          and run_directory(storage_root, second_run_id).is_dir(), second_run_id)
    check_pending_state("second run", state, second_run_id)
    status, _, state = send_http_request(port, "GET", f"/api/runs/{first_run_id}")
    check_recovered_state("first run unchanged by second", state, first_run_id, main_run["request_idea_id"], main_run["idea_id"])
    record_check("first run history/ledger bytes unchanged",
          read_history_file_bytes(storage_root, first_run_id) == first_run_history_bytes
          and ledger_path(storage_root, first_run_id).read_bytes() == first_run_ledger_bytes)


GIT_FAILURE_PREFIX = "<git failed"  # marks a snapshot field that git could not produce


@dataclass(frozen=True)
class RumiCheckoutSnapshot:
    """What the Rumi checkout looked like at one moment. Compared, never hard-coded.

    Clean public checkouts and checkouts with local changes are both valid; the suite
    only requires that it left the checkout exactly as it found it.
    """

    agent_py_sha256: str          # the file a local modification is known to touch
    head: str                     # `git rev-parse HEAD`
    status_porcelain: str         # `git status --porcelain=v1 --untracked-files=all`
    tracked_diff_sha256: str      # SHA-256 of `git diff HEAD --binary` (content of tracked edits)

    def git_fields(self) -> tuple[str, str, str]:
        return self.head, self.status_porcelain, self.tracked_diff_sha256

    def git_available(self) -> bool:
        return not any(field.startswith(GIT_FAILURE_PREFIX) for field in self.git_fields())


def _run_git(checkout_dir: Path, *args: str) -> bytes:
    # GIT_OPTIONAL_LOCKS=0: `git status` must not refresh/rewrite .git/index while we only look.
    completed = subprocess.run(["git", "-C", str(checkout_dir), *args], capture_output=True,
                               env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        return f"{GIT_FAILURE_PREFIX} ({completed.returncode}): {' '.join(args)}: {detail}>".encode()
    return completed.stdout


def capture_rumi_checkout_snapshot(checkout_dir: Path = RUMI_CHECKOUT_DIR) -> RumiCheckoutSnapshot:
    """Read-only snapshot of the Rumi checkout (hashes the file and asks git; writes nothing)."""
    agent_py_path = checkout_dir / "src" / "rumi" / "agent" / "agent.py"
    try:
        agent_py_sha256 = hashlib.sha256(agent_py_path.read_bytes()).hexdigest().upper()
    except OSError as exc:
        agent_py_sha256 = f"<unreadable: {exc}>"
    status = _run_git(checkout_dir, "status", "--porcelain=v1", "--untracked-files=all")
    tracked_diff = _run_git(checkout_dir, "diff", "HEAD", "--binary", "--no-ext-diff")
    return RumiCheckoutSnapshot(
        agent_py_sha256=agent_py_sha256,
        head=_run_git(checkout_dir, "rev-parse", "HEAD").decode("utf-8", "replace").strip(),
        status_porcelain=status.decode("utf-8", "replace"),
        tracked_diff_sha256=(tracked_diff.decode() if tracked_diff.startswith(GIT_FAILURE_PREFIX.encode())
                             else hashlib.sha256(tracked_diff).hexdigest()),
    )


def check_rumi_checkout_preserved(before: RumiCheckoutSnapshot,
                                  checkout_dir: Path = RUMI_CHECKOUT_DIR) -> None:
    """Two checks: the suite left agent.py, HEAD, status and tracked diff exactly as found."""
    after = capture_rumi_checkout_snapshot(checkout_dir)
    record_check("Rumi agent.py unchanged by the suite (SHA-256 before == after)",
                 after.agent_py_sha256 == before.agent_py_sha256 and not before.agent_py_sha256.startswith("<"),
                 {"before": before.agent_py_sha256, "after": after.agent_py_sha256})
    record_check("Rumi HEAD, git status and tracked diff unchanged by the suite",
                 before.git_available() and after.git_fields() == before.git_fields(),
                 {"note": "" if before.git_available() else "git unavailable: Rumi status cannot be verified",
                  "before": before.git_fields(), "after": after.git_fields()})  # note first: details are truncated
