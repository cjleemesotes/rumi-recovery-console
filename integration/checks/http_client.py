"""HTTP requests to the console under test; records every run id a POST /api/runs created."""
from __future__ import annotations

import http.client
import json

from integration.checks.results import RECORDER
from integration.workspace import LOOPBACK_HOST

__all__ = ["send_chunked_post", "send_http_request"]

HTTP_REQUEST_TIMEOUT_SECONDS = 60  # > two 15 s children plus queueing


def send_http_request(port: int, method: str, path: str, body: object = None, *, raw: bytes | None = None,
            headers: dict | None = None, timeout: float = HTTP_REQUEST_TIMEOUT_SECONDS):
    """Returns (status, headers{lower: value}, parsed JSON or text)."""
    connection = http.client.HTTPConnection(LOOPBACK_HOST, port, timeout=timeout)
    try:
        request_body = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        request_headers = dict(headers or {})
        if request_body is not None:
            request_headers.setdefault("Content-Type", "application/json")
        connection.request(method, path, body=request_body, headers=request_headers)
        response = connection.getresponse()
        response_bytes = response.read()
        response_headers = {header_name.lower(): header_value for header_name, header_value in response.getheaders()}
    finally:
        connection.close()
    response_text = response_bytes.decode("utf-8", "replace")
    if "json" in response_headers.get("content-type", ""):
        try:
            parsed_json = json.loads(response_text)
        except ValueError:
            parsed_json = None
        if parsed_json is not None:
            if (method == "POST" and path == "/api/runs" and response.status == 201
                    and isinstance(parsed_json, dict) and parsed_json.get("run_id")):
                RECORDER.created_run_ids.append(parsed_json["run_id"])
            return response.status, response_headers, parsed_json
    return response.status, response_headers, response_text


def send_chunked_post(port: int, path: str):
    connection = http.client.HTTPConnection(LOOPBACK_HOST, port, timeout=HTTP_REQUEST_TIMEOUT_SECONDS)
    try:
        connection.putrequest("POST", path)
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Transfer-Encoding", "chunked")
        connection.endheaders()
        connection.send(b"2\r\n{}\r\n0\r\n\r\n")
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()
