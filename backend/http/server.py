"""Server construction and lifecycle: exclusive loopback bind, serve, shutdown.

Two directories are involved and must not be confused:
  * code_root    - where ``frontend/`` (and the importable code) lives.
  * storage_root - where the runner keeps run data; defaults to code_root.
Per-request behavior lives in ``backend.http.request_handler``.
"""
from __future__ import annotations

import socket
import sys
from http.server import HTTPServer
from pathlib import Path

from backend.http.request_handler import ConsoleRequestHandler

__all__ = ["ExclusiveLoopbackServer", "make_server", "serve"]

LOOPBACK_HOSTS = {"127.0.0.1", "::1"}

# Windows only: SO_EXCLUSIVEADDRUSE forbids any other socket on the port.
SUPPORTS_EXCLUSIVE_BIND = hasattr(socket, "SO_EXCLUSIVEADDRUSE")


class ExclusiveLoopbackServer(HTTPServer):
    """HTTPServer that carries the two roots and never shares its port.

    Windows: SO_REUSEADDR would let a second process share the port, so it stays off and
    SO_EXCLUSIVEADDRUSE is used instead. POSIX: SO_REUSEADDR (no SO_REUSEPORT) only lets an
    immediate restart rebind past TIME_WAIT; a live listener still makes the bind fail.
    """

    allow_reuse_address = not SUPPORTS_EXCLUSIVE_BIND
    allow_reuse_port = False  # Never opt into concurrent listeners on one address/port.

    def __init__(self, address, request_handler_class, *, code_root: Path, storage_root: Path):
        self.code_root = Path(code_root)
        self.storage_root = Path(storage_root)
        if ":" in address[0]:
            self.address_family = socket.AF_INET6
        super().__init__(address, request_handler_class)

    def server_bind(self) -> None:
        # Set before bind so a second bind fails on Windows.
        if SUPPORTS_EXCLUSIVE_BIND:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_server(root: Path, host: str = "127.0.0.1", port: int = 8765, *,
                storage_root: Path | None = None) -> HTTPServer:
    """Bind (but do not serve) the console server. `root` is the absolute code root.

    Port 0 picks a free port (see `server.server_address`). Loopback hosts only.
    """
    if host not in LOOPBACK_HOSTS:
        raise ValueError(f"refusing non-loopback host {host!r}")
    code_root = Path(root)
    if not code_root.is_absolute():
        raise ValueError("root must be an absolute path")
    resolved_storage_root = Path(storage_root) if storage_root is not None else code_root
    return ExclusiveLoopbackServer((host, port), ConsoleRequestHandler,
                                   code_root=code_root, storage_root=resolved_storage_root)


def serve(root: Path, host: str = "127.0.0.1", port: int = 8765, *,
          storage_root: Path | None = None) -> None:
    """Bind and serve until interrupted; exit status 1 (naming host:port) if the bind fails."""
    try:
        server = make_server(root, host, port, storage_root=storage_root)
    except OSError as error:
        sys.stderr.write(f"Cannot bind {host}:{port}: {error}\n")
        raise SystemExit(1)
    bound_host, bound_port = server.server_address[:2]
    print(f"Rumi recovery console: http://{bound_host}:{bound_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
