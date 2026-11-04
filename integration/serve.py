"""Root launcher for the Rumi recovery console.

From the workspace root (C:\\Users\\leech\\test-agent-build):

    .\\Rumi\\.venv\\Scripts\\python.exe -m integration.serve

then open http://127.0.0.1:8765/. Optional flags exist for isolated checks only:

    --storage-root PATH   where .rumi-console/ lives (default: CODE_ROOT)
    --port N              loopback port (default 8765)
    --check               run the import preflight and exit (no listener)

CODE_ROOT (resolved once in `integration.workspace`) comes from the package
location, never from the shell cwd. Imports and static files always come from
CODE_ROOT; --storage-root only moves run state.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from integration.workspace import (
    CODE_ROOT,
    DEFAULT_PORT,
    LOOPBACK_HOST,
    RUMI_SOURCE_DIR,
    is_within_directory,
    prioritize_workspace_imports,
)

__all__ = ["CODE_ROOT", "DEFAULT_PORT", "EXIT_BIND_FAILED", "EXIT_PREFLIGHT_FAILED", "LOOPBACK_HOST",
           "PreflightError", "main", "preflight"]

EXIT_PREFLIGHT_FAILED = 3  # an import resolved to the wrong place or is missing
EXIT_BIND_FAILED = 1  # the loopback port could not be bound


class PreflightError(RuntimeError):
    pass


def preflight() -> dict:
    """Pin the intended checkout and verify every import the server needs."""
    if not RUMI_SOURCE_DIR.is_dir():
        raise PreflightError(f"Rumi checkout not found at {RUMI_SOURCE_DIR}")
    # Rumi/src first, then CODE_ROOT (for integration/, demo/, backend/).
    prioritize_workspace_imports()

    try:
        import rumi
        import rumi._core as rumi_core
    except Exception as exc:  # noqa: BLE001 — report any import failure plainly
        raise PreflightError(f"cannot import rumi / rumi._core: {exc!r}") from exc
    if not is_within_directory(rumi.__file__, RUMI_SOURCE_DIR / "rumi"):
        raise PreflightError(f"rumi resolved to {rumi.__file__}, expected under {RUMI_SOURCE_DIR}")
    if not is_within_directory(rumi_core.__file__, RUMI_SOURCE_DIR / "rumi"):
        raise PreflightError(f"rumi._core resolved to {rumi_core.__file__}, expected under {RUMI_SOURCE_DIR}")

    try:
        import demo
    except Exception as exc:  # noqa: BLE001
        raise PreflightError(f"cannot import demo: {exc!r}") from exc
    if not is_within_directory(getattr(demo, "__file__", None), CODE_ROOT / "demo"):
        raise PreflightError(
            f"demo resolved to {getattr(demo, '__file__', None) or list(demo.__path__)}, "
            f"expected {CODE_ROOT / 'demo' / '__init__.py'}"
        )
    # Locate (do not execute) the agent module and the child entry: the
    # server process never constructs a World/Cashier; children import them.
    import importlib.util
    for module_name in ("demo.cashier", "demo.worker", "demo.runner"):
        module_spec = importlib.util.find_spec(module_name)
        if module_spec is None or not is_within_directory(module_spec.origin, CODE_ROOT / "demo"):
            raise PreflightError(f"{module_name} not found under {CODE_ROOT / 'demo'} "
                                 f"(found {module_spec.origin if module_spec else None})")

    try:
        import backend.server as backend_server
    except Exception as exc:  # noqa: BLE001
        raise PreflightError(f"cannot import backend.server: {exc!r}") from exc
    if not is_within_directory(backend_server.__file__, CODE_ROOT / "backend"):
        raise PreflightError(f"backend.server resolved to {backend_server.__file__}")
    for name in ("serve", "make_server"):
        if not callable(getattr(backend_server, name, None)):
            raise PreflightError(f"backend.server.{name} is missing")

    return {
        "python": sys.executable,
        "version": sys.version.split()[0],
        "code_root": str(CODE_ROOT),
        "rumi": rumi.__file__,
        "rumi_core": rumi_core.__file__,
        "demo": demo.__file__,
        "backend": backend_server.__file__,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m integration.serve",
                                     description="Start the Rumi recovery console.")
    parser.add_argument("--storage-root", type=Path, default=None,
                        help="directory that holds .rumi-console/ (default: workspace root)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"loopback port (default {DEFAULT_PORT})")
    parser.add_argument("--check", action="store_true",
                        help="run the import preflight only, then exit")
    args = parser.parse_args(argv)

    if not 0 <= args.port <= 65535:
        parser.error("--port must be 0..65535")
    storage_root = None
    if args.storage_root is not None:
        storage_root = args.storage_root.resolve()
        storage_root.mkdir(parents=True, exist_ok=True)

    try:
        preflight_facts = preflight()
    except PreflightError as exc:
        print(f"PREFLIGHT FAILED: {exc}", file=sys.stderr, flush=True)
        return EXIT_PREFLIGHT_FAILED
    for key, value in preflight_facts.items():
        print(f"preflight {key}: {value}", file=sys.stderr, flush=True)
    print(f"preflight storage_root: {storage_root or CODE_ROOT}", file=sys.stderr, flush=True)
    if args.check:
        print("PREFLIGHT OK", flush=True)
        return 0

    import backend.server as backend_server
    try:
        backend_server.serve(CODE_ROOT, LOOPBACK_HOST, args.port, storage_root=storage_root)
    except OSError as exc:  # bind failures are normally reported by serve(); be safe
        print(f"Cannot bind {LOOPBACK_HOST}:{args.port}: {exc}", file=sys.stderr, flush=True)
        return EXIT_BIND_FAILED
    return 0


if __name__ == "__main__":
    sys.exit(main())
