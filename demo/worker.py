"""Stable CLI entry: ``python -X utf8 -m demo.worker <crash|inspect|recover> <run_dir>``.

``crash`` dies with exit 17 inside the tool (no output). ``inspect`` and ``recover``
print one JSON object on stdout and exit 0 (Rumi logs go to stderr). Storage paths
are derived from the validated run directory; nothing else is trusted. The phase
implementations live in ``demo.workers.phases``.
"""
from __future__ import annotations

import json
import os
import sys

from demo.runtime.contract import CRASH_ENV, LEDGER_ENV, WORKER_CRASH, WORKER_PHASES, ledger_path
from demo.workers.phases import (
    PHASE_HANDLERS, InvalidRunSetupError, resolve_validated_run_directory,
)

__all__ = ["main"]


def main(argv: list) -> int:
    if len(argv) != 2 or argv[0] not in WORKER_PHASES:
        print(f"usage: python -m demo.worker <{'|'.join(WORKER_PHASES)}> <run_dir>", file=sys.stderr)
        return 2
    phase, run_dir_arg = argv
    try:
        run_dir = resolve_validated_run_directory(run_dir_arg)
        os.environ[LEDGER_ENV] = str(ledger_path(run_dir))
        if phase != WORKER_CRASH:
            os.environ.pop(CRASH_ENV, None)
        result = PHASE_HANDLERS[phase](run_dir)
    except InvalidRunSetupError as exc:
        print(f"worker error: {exc}", file=sys.stderr)
        return 3
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
