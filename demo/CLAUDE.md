# demo/: crash, inspect and recover

Read `../CLAUDE.md` and the relevant parts of `../context/SPEC.md` before editing.
This is one deterministic payment scenario, with a real SQLite commit and process exit.

## Process sequence

Every phase runs as a separate `python -X utf8 -m demo.worker <phase> <absolute_run_dir>`.

- `start_run`: allocate storage -> crash (exit 17 after commit, no JSON) -> fresh inspect -> pending, counts 1/0/1.
- `recover_run`: fresh inspect -> retain original request ID -> recover child -> DIFFERENT fresh inspect -> recovered, counts 1/1/0.
- `inspect_run` and `current_state`: fresh inspect child for the selected run; current_state is idle when no run is selected.
- Repeat recovery must preserve the same result idea ID and write no extra history/row.

A child saying saved or exiting 0 is insufficient proof. Success needs independent inspection of persisted evidence.
Failed inspection can return an error State with unknown evidence and fresh_inspection=false.

## File map

- `runner.py`: stable public facade: start_run, current_state, inspect_run, recover_run, DemoError. Backend imports this.
- `worker.py`: stable CLI, validated run-directory setup and phase dispatch.
- `cashier.py`: Cashier, record_payment and open_agent; preserve their identity.
- `runtime/contract.py`: standard-library-only identity, environment names, paths, phases, timing policies, strict validators, error catalogue and DemoError.
- `runtime/storage.py`: run directories, atomic JSON, strict manifest validation, initial ledger creation.
- `runtime/children.py`: child-only environment and bounded subprocess execution; stdout JSON decoding.
- `runtime/state.py`: pure State construction and refusal/success classification.
- `runtime/orchestration.py`: the four public operations and the child sequence above.
- `workers/ledger.py`: read-only ledger access and classification; `workers/history.py`: original request and positional result inspection.
- `workers/phases.py`: child crash/inspect/recover implementations; these import Rumi and open a fresh World.

The parent runtime must not import workers, cashier or Rumi. Workers share only pure contract helpers with the parent.
For Rumi semantics and source locations, read `../context/RUMI_GUIDE.md`.

## Invariants

1. Cashier stays DEFINED in demo/cashier.py as `demo.cashier.Cashier`; moving and re-exporting changes persisted identity. Never run that file as __main__.
2. Preserve record_payment, agent ID till-1 and call ID call_pay_1. Address a recovered call by BOTH original request_idea_id and tool_call_id.
3. Each UUID run has separate run.json, ledger.sqlite3 and rumi/ history. Use contract path helpers; code root and storage root differ.
4. `build_child_env` changes a copy of the environment, not the server's os.environ. Use the same Python/agent identity/storage in every child; do not use -I (drops PYTHONPATH).
5. Exact expected keys/types matter. Float 42.0, boolean True, extra keys and contradictory manifest metadata must not pass as the supported demo.
6. Read ALL ledger rows using the read-only SQLite URI. Exactly one matching row is required. Absent, ambiguous, mismatched or unreadable evidence saves nothing.
7. Inspect/recover never invoke the payment tool or model. Never resume whirl after recovery, manually append history, delete evidence or invent a negative outcome.
8. The final inspection must find the literal recovered flag, exact confirmed result, one ledger row, zero pending calls and the same saved idea ID reported by recovery.

## Extension recipes (only within the requested scope)

- Error: add one `(message, HTTP status, phase or None)` entry to `ERROR_DEFINITIONS`; the three existing maps derive from it. Detect/map the condition where it occurs and preserve a useful State when possible.
- Ledger verdict: update classify_demo_payment_evidence AND the matching `record_<verdict>` error definition/state handling. Never let an unmapped verdict become success.
- Layout: add/change a contract path helper and its callers, not scattered path strings. Existing saved runs require compatibility.
- New State keys/phases or error vocabulary require coordinated SPEC/backend/frontend updates and isolated checks.
- Keep independent integration expectations; do not reuse app constants as their expected answers. Add no dependency for routine changes.

## Commands from the workspace root

```powershell
.\Rumi\.venv\Scripts\python.exe -m py_compile (Get-ChildItem demo -Recurse -Filter *.py).FullName
.\Rumi\.venv\Scripts\python.exe -m integration.test_flow --keep
.\Rumi\.venv\Scripts\python.exe -m integration.serve
```

Flow checks use temporary storage and another port. Do not edit walkthrough data for negative cases.
Reuse the listener on 8765; reload changed parent modules by restarting that owned server when needed.
For focused dependency checks, use the Rumi guide's commands. Preserve the existing dependency checkout and local modifications.
