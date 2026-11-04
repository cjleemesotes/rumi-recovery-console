"""Stable public entry for the backend: the four runner operations and ``DemoError``.

Each operation takes ``storage_root`` (where ``.rumi-console/`` lives; imports and
static files always come from the code root) and returns the State dict. The
implementation lives in ``demo.runtime``; this module never imports Rumi.
"""
from __future__ import annotations

from demo.runtime.contract import DemoError
from demo.runtime.orchestration import current_state, inspect_run, recover_run, start_run

__all__ = ["DemoError", "current_state", "inspect_run", "recover_run", "start_run"]
