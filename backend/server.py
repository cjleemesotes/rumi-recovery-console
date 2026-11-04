"""Stable public entry point of the backend: ``make_server`` and ``serve``.

The implementation lives in ``backend.http`` (see backend/README.md).
"""
from __future__ import annotations

from backend.http.server import make_server, serve

__all__ = ["make_server", "serve"]
