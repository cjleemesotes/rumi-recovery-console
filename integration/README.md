# integration/

This folder holds the root launcher and the complete-flow checks for the Rumi recovery console. Run every command from the repository root after following the root README's setup.

The optional [Cloudflare hosting bridge](hosting/README.md) serves the frontend at
`mineai.net/recovery-agent/` and connects a separate public demo instance on this PC.

## Commands (unchanged)

```powershell
.\Rumi\.venv\Scripts\python.exe -m integration.serve                     # start the console on http://127.0.0.1:8765/
.\Rumi\.venv\Scripts\python.exe -m integration.serve --check             # import preflight only, then exit
.\Rumi\.venv\Scripts\python.exe -m integration.test_flow                 # complete-flow checks; exit 0 = all passed
.\Rumi\.venv\Scripts\python.exe -m integration.test_flow --keep          # keep the temporary artifacts
.\Rumi\.venv\Scripts\python.exe -m integration.test_flow --edges-only    # only the false-success probes (~75 s)
```

`serve` also takes `--storage-root PATH`, which moves `.rumi-console\` (the run state), and `--port N`. Both exist only for isolated checks. Imports and static files never move.

Before binding, the launcher's preflight checks that:

- `rumi` and `rumi._core` load from `Rumi\src`
- `demo` and `backend.server` load from this workspace

If the preflight fails, it exits with code 3. If the port is already taken, it exits nonzero and names `host:port`. The bind is exclusive on Windows, and there is no fallback to another port.

## Folder map

| File | Role |
|---|---|
| `workspace.py` | Resolves `CODE_ROOT`, `RUMI_SOURCE_DIR`, `LOOPBACK_HOST` and `DEFAULT_PORT`, plus the sys.path helpers. This is the only place that resolves the code root, so moving modules doesn't change cwd, imports or storage. |
| `serve.py` | Stable launcher entry point: `preflight()`, `main()`, `PreflightError`. |
| `test_flow.py` | Stable test entry point. It prioritizes workspace imports, then runs `checks.suite.main`. |
| `checks/results.py` | The one shared `RECORDER` (check results and created run ids), plus `record_check`, `record_check_or_abort` and `SectionAborted`. |
| `checks/expectations.py` | Expected agent identity, payment arguments, recovered result, State fields and run-id pattern. |
| `checks/storage.py` | Reads, and deliberately tampers with, one isolated run's history, ledger and `run.json`. |
| `checks/assertions.py` | State-shape, pending and recovered State checks, and on-disk pending evidence. |
| `checks/http_client.py` | HTTP and chunked requests to the console under test. Records the runs each POST creates. |
| `checks/processes.py` | `LauncherProcess`: starts, probes and stops real `-m integration.serve` processes. |
| `checks/flow_scenarios.py` | Startup, static files and idle state; exclusive bind; crash, inspect, recover, repeat and refresh; restart; new-run isolation; preserved Rumi checkout. |
| `checks/refusal_scenarios.py` | Refusals for absent, duplicate, mismatched or unreadable ledger rows; unsupported history; false-success edges; invalid bodies, IDs, methods and routes. |
| `checks/suite.py` | Run orchestration: temp storage plus a free port, section order, summary and exit code. |

Within `checks/`, each module imports only the modules listed above it, so there are no cycles. The suite depends on the other folders only through their public interfaces:

- the `-m integration.serve` command
- the HTTP routes and State JSON
- the run files on disk (`run.json`, `ledger.sqlite3`, `rumi/` history)
- Rumi's public `FilesystemTablet` and `TextIdea`

## About the checks

The checks start the real launcher on a temporary storage root and a free port. They never use 8765 or the walkthrough data. A full run has 304 checks and takes about 3–4 minutes. They cover:

- the crash, inspection that leaves history unchanged, recovery, repeated recovery, refresh, server restart, and a second separate run
- refusals for ledger rows that are absent, duplicated, mismatched or unreadable, and for unsupported history
- false-success edges: a `recovered` flag that isn't literally `True`, a contradictory `run.json`, and an unknown or wrong worker exit code
- invalid bodies, IDs and methods
- exclusive binding
- the Rumi checkout left unchanged, whether clean or locally modified at startup

Don't run the checks during a browser walkthrough.
