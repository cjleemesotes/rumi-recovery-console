"""Run orchestration: isolated temp storage + free port, section order, summary, exit code.

`main(argv)` is what `python -m integration.test_flow [--keep] [--edges-only]` runs.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from integration.checks.flow_scenarios import (
    capture_rumi_checkout_snapshot,
    check_bind_exclusivity,
    check_crash_inspect_recover_flow,
    check_new_run_isolation,
    check_restart_preserves_recovery,
    check_rumi_checkout_preserved,
    check_static_assets_and_idle_state,
)
from integration.checks.processes import LOG_TAIL_CHARS, LauncherProcess, find_free_loopback_port
from integration.checks.refusal_scenarios import (
    check_evidence_refusals,
    check_false_success_edges,
    check_invalid_requests,
)
from integration.checks.results import RECORDER, SectionAborted, record_check
from integration.checks.storage import runs_directory
from integration.workspace import CODE_ROOT

__all__ = ["main"]

PREFLIGHT_TIMEOUT_SECONDS = 60  # one `-m integration.serve --check` on a cold interpreter

SectionResult = TypeVar("SectionResult")


def _run_section(name: str, section: Callable[[], SectionResult]) -> SectionResult | None:
    """Run one scenario group and return its result.

    `SectionAborted` (a failed precondition, already recorded) ends only this group.
    Any other exception is recorded as a failed check and the suite continues.
    """
    try:
        return section()
    except SectionAborted:
        return None
    except Exception:  # noqa: BLE001 — record it, then run the next group
        record_check(f"{name}: no unexpected exception", False, traceback.format_exc())
        return None


def _check_runs_stay_in_isolated_storage(storage_root: Path) -> None:
    runs_root = runs_directory(storage_root)
    run_ids_on_disk = sorted(run_path.name for run_path in runs_root.glob("*")) if runs_root.exists() else []
    created_run_ids = sorted(RECORDER.created_run_ids)
    record_check("every run this check created lives in the isolated STORAGE_ROOT",
                 created_run_ids == run_ids_on_disk and len(run_ids_on_disk) > 0,
                 (created_run_ids, run_ids_on_disk))


def _print_summary(started_at: float) -> bool:
    """Print the totals and every failed check name; True when all checks passed."""
    failed_checks = RECORDER.failed_results()
    print(f"\n{len(RECORDER.results) - len(failed_checks)}/{len(RECORDER.results)} checks passed in "
          f"{time.monotonic() - started_at:.1f}s", flush=True)
    for _, name, _ in failed_checks:
        print(f"  FAILED: {name}", flush=True)
    return not failed_checks


def main(argv: list[str]) -> int:
    keep_artifacts = "--keep" in argv
    edges_only = "--edges-only" in argv
    RECORDER.reset()
    # Baseline of the Rumi checkout as found, before preflight or any scenario can touch it.
    rumi_checkout_before = capture_rumi_checkout_snapshot()
    started_at = time.monotonic()
    temp_root = Path(tempfile.mkdtemp(prefix="rumi-console-flow-"))
    storage_root, log_dir = temp_root / "storage", temp_root / "logs"
    storage_root.mkdir()
    log_dir.mkdir()
    port = find_free_loopback_port()
    print(f"test_flow: CODE_ROOT={CODE_ROOT}\n           STORAGE_ROOT={storage_root} port={port}", flush=True)

    preflight_result = subprocess.run([sys.executable, "-m", "integration.serve", "--check"], cwd=str(CODE_ROOT),
                                      capture_output=True, text=True, encoding="utf-8",
                                      timeout=PREFLIGHT_TIMEOUT_SECONDS)
    record_check("launcher preflight (--check) passes", preflight_result.returncode == 0,
                 preflight_result.stderr[-LOG_TAIL_CHARS:])

    # `launcher` always names the process currently serving, so `finally` stops the
    # right one even after the restart scenario replaced it.
    launcher = LauncherProcess(storage_root, port, log_dir, "main")
    launcher.start()
    try:
        server_ready = record_check("server starts on isolated storage + alternate port",
                                    launcher.wait_until_serving(), launcher.read_log_tail())
        if server_ready and edges_only:
            _run_section("false-green edges", lambda: check_false_success_edges(launcher))
        elif server_ready:
            _run_section("static/idle", lambda: check_static_assets_and_idle_state(port))
            _run_section("bind exclusivity", lambda: check_bind_exclusivity(storage_root, port, log_dir))
            main_run = _run_section("main flow", lambda: check_crash_inspect_recover_flow(launcher))
            if main_run:
                launcher = _run_section(
                    "restart", lambda: check_restart_preserves_recovery(launcher, log_dir, main_run)) or launcher
                _run_section("new run", lambda: check_new_run_isolation(launcher, main_run))
                _run_section("invalid requests", lambda: check_invalid_requests(launcher, main_run))
            _run_section("refusals", lambda: check_evidence_refusals(launcher))
            _run_section("false-green edges", lambda: check_false_success_edges(launcher))
            _check_runs_stay_in_isolated_storage(storage_root)
    finally:
        launcher.stop()
    check_rumi_checkout_preserved(rumi_checkout_before)

    all_passed = _print_summary(started_at)
    if not all_passed or keep_artifacts:
        print(f"artifacts kept at {temp_root}", flush=True)
    else:
        shutil.rmtree(temp_root, ignore_errors=True)
    return 0 if all_passed else 1
