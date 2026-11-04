"""Check results and run tracking shared by every check module.

All state lives on the single `RECORDER` object. Modules import that object and
mutate it; nothing rebinds module-level lists, so every importer sees one log.
"""
from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["CheckRecorder", "RECORDER", "SectionAborted", "record_check", "record_check_or_abort"]

DETAIL_CHARS = 900  # failure detail kept per check, so one huge State cannot flood the log


@dataclass
class CheckRecorder:
    """Every recorded check (passed, name, detail) and every run id the suite created."""

    results: list[tuple[bool, str, str]] = field(default_factory=list)
    created_run_ids: list[str] = field(default_factory=list)

    def reset(self) -> None:
        """Forget earlier results in place, so each suite run reports only its own checks."""
        self.results.clear()
        self.created_run_ids.clear()

    def failed_results(self) -> list[tuple[bool, str, str]]:
        return [check_result for check_result in self.results if not check_result[0]]


RECORDER = CheckRecorder()


def record_check(name: str, passed: bool, detail: object = "") -> bool:
    RECORDER.results.append((bool(passed), name, "" if passed else str(detail)[:DETAIL_CHARS]))
    status_label = "PASS" if passed else "FAIL"
    print(f"[{status_label}] {name}" + ("" if passed else f"\n       -> {str(detail)[:DETAIL_CHARS]}"), flush=True)
    return bool(passed)


class SectionAborted(Exception):
    """A precondition for the remaining steps of a section failed."""


def record_check_or_abort(name: str, passed: bool, detail: object = "") -> None:
    if not record_check(name, passed, detail):
        raise SectionAborted(name)
