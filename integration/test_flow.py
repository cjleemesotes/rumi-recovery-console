"""Complete-flow checks for the Rumi recovery console (HTTP, real processes).

Run from the workspace root:

    .\\Rumi\\.venv\\Scripts\\python.exe -m integration.test_flow [--keep] [--edges-only]

Every check launches the real root launcher (`-m integration.serve`) on an
ISOLATED temporary --storage-root and an alternate free port, so the
walkthrough server on 8765 and its .rumi-console/ data are never touched.
Imports/static files still come from CODE_ROOT. Exit code 0 = all passed.

This module is only the stable command entry point; the checks live in
`integration/checks/` (see that package's docstring for the module map).
"""
from __future__ import annotations

import sys

from integration.workspace import prioritize_workspace_imports

prioritize_workspace_imports()  # before any module that imports rumi

from integration.checks.suite import main  # noqa: E402

__all__ = ["main"]

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
