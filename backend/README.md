# backend

Thin, stdlib-only HTTP adapter around `demo.runner`. No recovery or ledger logic lives here.

| File | Role |
|---|---|
| `server.py` | Stable public entry: `make_server(root, host, port, *, storage_root=None)` and `serve(...)`. Used by `integration/serve.py`. |
| `http/server.py` | Exclusive loopback bind (Windows `SO_EXCLUSIVEADDRUSE`), `make_server`, `serve`, lifecycle. |
| `http/request_handler.py` | Per-request work: routing, 404/405, POST body rules, static allow-list, JSON replies, calls to `demo.runner`. |

`root` is the code root (holds `frontend/`); `storage_root` (default: `root`) is only forwarded to the runner.
Static map: `/` -> `frontend/index.html`, `/app.js` -> `frontend/assets/js/console.js`, `/styles.css` -> `frontend/assets/css/console.css`.

Note: the sub-package is named `http`; always import it as `backend.http...` and never put `backend/` itself on `sys.path`, or it would shadow the standard library `http`.
