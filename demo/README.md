# demo/ — Cashier crash demo and recovery runner

Public entries (stable; other packages use only these):
- `demo/runner.py` — `start_run`, `current_state`, `inspect_run`, `recover_run`, `DemoError`. Used by `backend/`.
- `demo/worker.py` — CLI `python -X utf8 -m demo.worker <crash|inspect|recover> <run_dir>`; run only as a child process.
- `demo/cashier.py` — `Cashier`, `record_payment`, `open_agent`. Module identity is persisted (`demo.cashier.Cashier`); never move or rename it, and never run it as `__main__`.

`demo/runtime/` — parent side, never imports Rumi or Cashier:
- `contract.py` — identity, environment names, storage-path helpers, phases, timing policies, strict payment/result validators, the single error catalogue and `DemoError`. Standard library only; shared by parent and child.
- `storage.py` — run directories, atomic JSON, strict `run.json` validation, fixture ledger creation.
- `children.py` — builds the child-only environment and runs worker phases with a 15 s timeout.
- `state.py` — pure State snapshot construction and error/State helpers.
- `orchestration.py` — the four operations (start / current / inspect / recover).

`demo/workers/` — child side, imports Rumi and Cashier:
- `ledger.py` — read-only SQLite access and evidence classification.
- `history.py` — locate and decode the original stored request and its results.
- `phases.py` — the `crash`, `inspect` and `recover` phases and run-directory validation.

Dependencies: `runtime.contract` <- `runtime.state` <- `runtime.storage`; `runtime.children` <- `runtime.orchestration`; `workers.*` and `cashier` import only `runtime.contract` from the parent side. No cycles.
