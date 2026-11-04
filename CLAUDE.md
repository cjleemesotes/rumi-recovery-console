# Rumi recovery console: working guide

## Start here

This is one local, deterministic demo of recovering an interrupted Rumi tool call.
The model response is mocked; the SQLite commit, process exit and recovery are real.
Read the relevant folder's `CLAUDE.md`, then inspect its source before changing it.
`context/SPEC.md` defines the public contract. `README.md` and folder READMEs map the code.
`context/CONTEXT.md` contains verified background and dated completion records, not a new task.

## Commands (PowerShell, workspace root)

```powershell
.\Rumi\.venv\Scripts\python.exe -m integration.serve          # http://127.0.0.1:8765/
.\Rumi\.venv\Scripts\python.exe -m integration.serve --check  # imports only, no listener
.\Rumi\.venv\Scripts\python.exe -m integration.test_flow --keep
```

Use that Python executable. Bare `python` can select an unrelated Rumi installation.
The prepared workspace needs no frontend build, installation, live model key or Rust rebuild. For a fresh clone, follow README.md's submodule/environment setup first.
Reuse an existing console listener; do not start another on the same port.
Flow checks select temporary storage and another port; never corrupt walkthrough data to test refusals.

## Ownership and entrypoints

| Area | Entry / responsibility | Read next |
| --- | --- | --- |
| `frontend/` | `index.html`, `assets/js/console.js`, `assets/css/console.css`; browser view | `frontend/CLAUDE.md` |
| `backend/` | `server.py` facade; `http/` serves API and exact static allow-list | `backend/CLAUDE.md` |
| `demo/` | `runner.py` facade, `worker.py` CLI, `cashier.py` agent/tool; runtime and workers | `demo/CLAUDE.md` |
| `integration/` | `serve.py` launcher, `test_flow.py` check command, `checks/` | `integration/CLAUDE.md` |
| `Rumi/` | Existing dependency; preserve its checkout and local modifications | `context/RUMI_GUIDE.md` |

The small facade modules are compatibility boundaries, not dead code.
Keep the five existing top-level application/dependency folders.
Do not change Rumi source unless a reproducible blocker requires a narrowly scoped fix.

## Recovery rules that must survive every edit

- `demo.cashier.Cashier` must stay defined in `demo/cashier.py`. Its module-qualified name is persisted identity; a re-export from a moved class is insufficient.
- Each new run uses its own UUID directory, SQLite ledger and Rumi history. Code location and storage location are separate concerns.
- The tool commits exactly one demo payment, then its worker exits with code 17 before returning a result. A simulated exception is not this demo.
- The parent demo runtime orchestrates children without importing Rumi/Cashier. Each worker opens a fresh World using the same class, agent ID and storage. Launcher preflight may import Rumi to check its origin.
- Recovery reads the original stored request and checks all ledger rows. Missing, ambiguous, mismatched or unreadable evidence remains unresolved; never guess an outcome.
- Recovery never runs the payment tool or calls the model. Save through Rumi's recovery API, then require a DIFFERENT fresh inspection to confirm the saved result, one row and zero pending calls.
- Preserve the original request and result idea IDs. Repeated recovery must return the same result with no extra row/history write; refresh and restart preserve it.
- Keep unknown evidence as unknown, not zero. Show refusals and uncertainty plainly. Never automatically retry a POST.

## Make small, verifiable changes

1. Follow the request into its owning module. Read functions and call sites; cite real file/function names when explaining behavior.
2. Shared demo paths, identity, phases, strict validators, policy limits and the error catalogue belong in `demo/runtime/contract.py` (standard library only).
3. Keep HTTP transport, parent orchestration, child recovery and DOM rendering separate. Use public entrypoints across folders.
4. Name non-obvious policies with units. Keep boundary validation even where two layers check similar inputs. Do not turn every display label or JSON key into a constant.
5. Keep integration expectations independent of app constants so a wrong app value cannot validate itself.
6. Run checks appropriate to changed behavior. App-flow changes need the isolated complete flow; frontend changes also need browser inspection. Documentation-only work needs fact/link review, not a claim that unrun tests passed.
7. Report what changed, checks actually run and remaining uncertainty. Comprehension/review tasks do not authorize source edits or new product features.

Do not load historical worker reports, evaluation answer keys or runtime data merely to explain the code. Inspect current source; read extra context only when the task needs it.
