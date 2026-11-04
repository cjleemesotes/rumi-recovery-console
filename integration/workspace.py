"""The workspace's fixed locations and loopback address, resolved in one place.

CODE_ROOT is derived from this file's location, never from the shell cwd, so
moving modules inside integration/ does not change imports, child cwd, static
files or the default storage root. Imports and static files always come from
CODE_ROOT; only `--storage-root` moves run state.
"""
from __future__ import annotations

import sys
from pathlib import Path

__all__ = [
    "CODE_ROOT",
    "DEFAULT_PORT",
    "LOOPBACK_HOST",
    "RUMI_CHECKOUT_DIR",
    "RUMI_SOURCE_DIR",
    "is_within_directory",
    "prioritize_workspace_imports",
]

CODE_ROOT = Path(__file__).resolve().parent.parent
RUMI_CHECKOUT_DIR = CODE_ROOT / "Rumi"
RUMI_SOURCE_DIR = RUMI_CHECKOUT_DIR / "src"
LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def is_within_directory(path: str | Path | None, directory: Path) -> bool:
    """True when `path` resolves to `directory` or somewhere beneath it."""
    if not path:
        return False
    try:
        Path(path).resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def _move_to_front_of_sys_path(directory: Path) -> None:
    """Put `directory` first on sys.path, removing any equivalent existing entry."""
    resolved_directory = str(directory.resolve()).lower()
    normalized_sys_path = [str(Path(path_entry).resolve()).lower() if path_entry else ""
                           for path_entry in sys.path]
    if resolved_directory in normalized_sys_path:
        sys.path.pop(normalized_sys_path.index(resolved_directory))
    sys.path.insert(0, str(directory))


def prioritize_workspace_imports() -> None:
    """Import `rumi` from CODE_ROOT/Rumi/src and integration/demo/backend from CODE_ROOT."""
    _move_to_front_of_sys_path(CODE_ROOT)
    _move_to_front_of_sys_path(RUMI_SOURCE_DIR)
