"""Request handling for the console: routing, body rules, static files, JSON replies.

Everything here is per-request. Binding and lifecycle live in ``backend.http.server``.
The handler expects ``self.server`` to provide ``code_root`` (where ``frontend/``
lives) and ``storage_root`` (passed through to ``demo.runner``).
"""
from __future__ import annotations

import json
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import urlsplit

from demo import runner as demo_runner

__all__ = [
    "ConsoleRequestHandler",
    "HttpError",
    "MAX_REQUEST_BODY_BYTES",
    "CLIENT_READ_TIMEOUT_SECONDS",
    "RUN_ID_PATTERN",
    "STATIC_FILES",
]

RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
MAX_REQUEST_BODY_BYTES = 4096
# Idle speculative browser sockets must not block the single server thread forever.
CLIENT_READ_TIMEOUT_SECONDS = 5

# URL path -> (file path relative to code_root/frontend, Content-Type header). Exact allow-list.
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("assets/js/console.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("assets/css/console.css", "text/css; charset=utf-8"),
}


class HttpError(Exception):
    """A request problem answered with an error-only JSON envelope."""

    def __init__(self, status: int, code: str, message: str, allowed_methods: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.allowed_methods = allowed_methods  # sent as the Allow header on 405


class ConsoleRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # close the connection after every response
    timeout = CLIENT_READ_TIMEOUT_SECONDS
    server_version = "RumiConsole"
    sys_version = ""

    # ---- response helpers ----

    def log_message(self, message_format, *message_args):  # one terse line to stderr
        sys.stderr.write("[console] %s - %s\n" % (self.address_string(), message_format % message_args))

    def _send_bytes(self, status: int, body: bytes, content_type: str,
                    extra_headers: dict | None = None) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            for header_name, header_value in (extra_headers or {}).items():
                self.send_header(header_name, header_value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except OSError:  # broken pipe, reset, timeout: the client went away
            self.close_connection = True

    def _send_json(self, status: int, payload: Any, extra_headers: dict | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8", extra_headers)

    def _send_error_envelope(self, status: int, code: str, message: str,
                             extra_headers: dict | None = None) -> None:
        self._send_json(status, {"error": {"code": code, "message": message}}, extra_headers)

    # ---- routing ----

    @staticmethod
    def _match_route(path: str):
        """Return (allowed_methods, action, run_id) for a known path, else None (-> 404).

        `action` is one of: static, state, start, inspect, recover.
        """
        if path in STATIC_FILES:
            return ("GET",), "static", None
        if path == "/api/state":
            return ("GET",), "state", None
        if path == "/api/runs":
            return ("POST",), "start", None
        inspect_match = re.fullmatch(r"/api/runs/([^/]+)", path)
        if inspect_match:
            return ("GET",), "inspect", inspect_match.group(1)
        recover_match = re.fullmatch(r"/api/runs/([^/]+)/recover", path)
        if recover_match:
            return ("POST",), "recover", recover_match.group(1)
        return None

    def _handle_request(self, method: str) -> None:
        path = urlsplit(self.path).path  # query strings are ignored for routing
        try:
            route = self._match_route(path)
            if route is None:
                raise HttpError(404, "not_found", "Not found.")
            allowed_methods, action, run_id = route
            if method not in allowed_methods:
                raise HttpError(405, "method_not_allowed", "Method not allowed.",
                                allowed_methods=", ".join(allowed_methods))
            if action == "static":
                return self._serve_static_file(path)
            if method == "POST":
                self._require_empty_json_object_body()
            if run_id is not None and not RUN_ID_PATTERN.fullmatch(run_id):
                raise HttpError(400, "invalid_request", "Invalid run id.")
            self._run_demo_action(action, run_id)
        except HttpError as error:
            allow_header = {"Allow": error.allowed_methods} if error.allowed_methods else None
            self._send_error_envelope(error.status, error.code, error.message, allow_header)
        except TimeoutError:
            self.close_connection = True
        except Exception:  # never leak internals to the client
            traceback.print_exc(file=sys.stderr)
            self._send_error_envelope(500, "internal_error", "Internal server error.")

    def _require_empty_json_object_body(self) -> None:
        """POST bodies must be absent or exactly `{}`: clients never supply outcomes."""
        if self.headers.get("Transfer-Encoding") is not None:
            raise HttpError(400, "invalid_request", "Transfer-encoded bodies are not accepted.")
        content_length_header = (self.headers.get("Content-Length") or "").strip()
        if not content_length_header:
            return
        try:
            content_length = int(content_length_header)
        except ValueError:
            raise HttpError(400, "invalid_request", "Invalid Content-Length.")
        if content_length < 0:
            raise HttpError(400, "invalid_request", "Invalid Content-Length.")
        if content_length > MAX_REQUEST_BODY_BYTES:
            raise HttpError(413, "payload_too_large", "Request body too large.")
        if content_length == 0:
            return
        body_bytes = self.rfile.read(content_length)
        try:
            parsed_body = json.loads(body_bytes.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise HttpError(400, "invalid_request", "Body must be valid UTF-8 JSON.")
        if not isinstance(parsed_body, dict):
            raise HttpError(400, "invalid_request", "Body must be a JSON object.")
        if parsed_body:
            raise HttpError(400, "invalid_request",
                            "This endpoint accepts only an empty JSON object; outcomes, "
                            "results, arguments and paths are never client-supplied.")

    def _serve_static_file(self, path: str) -> None:
        relative_file, content_type = STATIC_FILES[path]
        try:
            body = (self.server.code_root / "frontend" / relative_file).read_bytes()
        except OSError:
            raise HttpError(404, "not_found", "Not found.")
        self._send_bytes(200, body, content_type)

    def _run_demo_action(self, action: str, run_id: str | None) -> None:
        """Call the matching demo.runner function and send its State (or error) as JSON."""
        storage_root = self.server.storage_root
        success_status = 200
        try:
            if action == "state":
                state = demo_runner.current_state(storage_root)
            elif action == "start":
                state, success_status = demo_runner.start_run(storage_root), 201
            elif action == "inspect":
                state = demo_runner.inspect_run(storage_root, run_id)
            else:
                state = demo_runner.recover_run(storage_root, run_id)
        except demo_runner.DemoError as error:
            if isinstance(error.state, dict):  # a fresh State carrying its own error field
                return self._send_json(error.http_status, error.state)
            return self._send_error_envelope(error.http_status, error.code, error.message)
        if not isinstance(state, dict):
            raise TypeError(f"demo.runner action {action!r} returned {type(state).__name__}, not dict")
        self._send_json(success_status, state)

    # Method hooks required by BaseHTTPRequestHandler; all go through one dispatcher
    # so unsupported methods get the same 404/405 treatment.
    def do_GET(self): self._handle_request("GET")
    def do_POST(self): self._handle_request("POST")
    def do_HEAD(self): self._handle_request("HEAD")
    def do_PUT(self): self._handle_request("PUT")
    def do_DELETE(self): self._handle_request("DELETE")
    def do_PATCH(self): self._handle_request("PATCH")
    def do_OPTIONS(self): self._handle_request("OPTIONS")
