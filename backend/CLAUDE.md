# backend/: HTTP adapter

Read `../CLAUDE.md` for shared rules. Public HTTP/State behavior is in `../context/SPEC.md`.
This layer translates HTTP to `demo.runner`; keep recovery, SQLite and subprocess logic out.
Backend modules and the parent demo runtime do not import Rumi; launcher preflight separately checks its origin.

## Layout and imports

- `server.py`: stable facade, exporting `make_server` and `serve` for the launcher.
- `http/server.py`: `ExclusiveLoopbackServer`, binding and lifecycle. `make_server` binds only; `serve` runs and closes it.
- `http/request_handler.py`: `ConsoleRequestHandler`, `HttpError`, routes, POST validation, static allow-list and JSON responses.
- Import direction: facade -> server -> request handler -> `demo.runner`. Use public entrypoints across folders.
- Always import `backend.http...`. Never add `backend/` itself to sys.path: its http/ would shadow Python's standard library.
- Public signatures stay `(root, host="127.0.0.1", port=8765, *, storage_root=None)`.

## Two roots

- `root` / `code_root` is the absolute code directory holding frontend/.
- `storage_root` defaults to root and is forwarded to runner calls; it selects run data, never imports or assets.

## Request path

`_handle_request` matches the route, checks the method, validates POST bodies, validates a run ID, then dispatches.
Routes: GET /api/state, POST /api/runs (success 201), GET /api/runs/{id}, POST /api/runs/{id}/recover.
Query strings are ignored; trailing-slash alternatives are 404. Known route + wrong method is 405 with Allow.
Run IDs must be exactly 32 lowercase hex characters; invalid IDs are 400.

`STATIC_FILES` is an exact GET allow-list, relative to code_root/frontend:

- `/` -> index.html
- `/app.js` -> assets/js/console.js
- `/styles.css` -> assets/css/console.css

Missing/unreadable assets give a 404 JSON error; never interpret a URL as an arbitrary file path.

## Policies and errors

- HTTP/1.0, close connections, no-store responses, 5-second client read timeout. The server is single-threaded.
- POST accepts no body, a zero-length body, or a JSON empty object. Clients never supply results, arguments or paths.
- Transfer-Encoding, invalid/negative Content-Length, malformed UTF-8/JSON, non-object or nonempty object: 400 invalid_request.
- More than `MAX_REQUEST_BODY_BYTES` (4096): 413 payload_too_large.
- Error-only response shape: `{"error":{"code":"...","message":"..."}}`.
- A `DemoError` with a dict State sends that State at its http_status; otherwise send its error envelope.
- Unexpected exceptions or a non-dict runner return produce 500 internal_error; traceback stays on stderr.
- Loopback hosts only; non-loopback host or relative code root raises ValueError. Port 0 selects an ephemeral port.
- Windows uses exclusive binding before bind; a second server fails. `serve` reports bind failure and exits 1.
- POSIX enables address reuse for immediate restart after TIME_WAIT. Port reuse stays disabled, so a second live listener still fails.

## Change and check

For an authorized contract change, update SPEC and coordinate the runner/frontend. Add routes in `_match_route` and actions in `_run_demo_action`; keep domain decisions in the runner. Put body validation in `_require_empty_json_object_body`, assets in `STATIC_FILES`, and meaningful policy constants near their use.

From the workspace root:

```powershell
.\Rumi\.venv\Scripts\python.exe -m py_compile backend\http\request_handler.py backend\http\server.py
.\Rumi\.venv\Scripts\python.exe -m integration.test_flow --keep
```

For a focused HTTP check, use `make_server(absolute_code_root, port=0, storage_root=temp_directory)` and clean up the test server. Never use the walkthrough's storage for refusal tests.
