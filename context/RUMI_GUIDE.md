# Rumi dependency guide (for coding agents)

Source-grounded facts about `Rumi/`, the existing dependency checkout. Root `README.md`, `context/SPEC.md` and `context/CONTEXT.md` stay authoritative.

**Change policy:** preserve the checkout and its local uncommitted changes (check `git -C Rumi status --short`). Do not edit `Rumi/` for docs, app or evaluation work. Only a demonstrated, reproducible blocker authorizes a narrowly scoped fix, and the coordinator decides that. Otherwise report the problem.

## What it is
A slim agent library. A `Dervish` (agent) calls a model through a `Heart`, runs `@tool` functions, and saves its history as "ideas" on a `Tablet` (JSON files). `from rumi import ...` exposes `Dervish, World, HeartConfig, Voice, tool, TextIdea, ToolRequestIdea, ToolResultIdea` and the recovery types (`src/rumi/api.py`). `whirl(message)` runs one model/tool cycle. It needs the native `_core` extension: a fresh clone builds it during README setup, while the prepared workspace already has it. Do not rebuild it for routine console work.

## Identity (the most common mistake)
- An agent is `(World, agent_type, agent_id)`. `agent_type` is the module-qualified class name, e.g. `demo.cashier.Cashier` (`agent/agent.py`, `_qualified_agent_name`). It also names the folder: `<data_dir>/<agent_type>/<agent_id>/history/<idea-id>.json`.
- The class must be defined under the same module path in every process. Defining or running it as `__main__`, moving it, or defining it in a submodule changes the type and hides stored history. Re-exporting does not help (`__module__` is where it is defined).
- `agent_id` is a non-blank string that contains no `/` or `\` and is not `.` or `..` (`agent.py`, `__init__` checks). The local edit makes it optional: omitting it mints a random `auto-<hex>` id, i.e. a brand-new empty history. Recovery is still possible if that id is retained and reused, but a caller that relies on the default can silently select a different history. This workspace must pass `till-1` explicitly every time.
- Do not confuse ids: agent id, request idea id (`ToolRequestIdea.id`), tool call id (`call_pay_1`), result idea id. Tool call ids are only unique within one request, so address a call by `(request_idea_id, tool_call_id)`.

## Fresh World / fresh process
- Agent instances are cached per `World` (`agent/registry.py`) and load history at construction (`_replay_history`); they do not refresh their in-memory history after another process writes. Recovery checks disk for stale history rather than reloading it. To inspect the new history, create a new `World` (or new process) and construct the agent again.
- Rumi assumes one writer per agent. Recording from a stale instance raises `UnsupportedRecoveryError` with `reason="stale_history"` and writes nothing.
- This workspace runs every inspect/recover step in a separate `python -m demo.worker` child. The parent demo runtime (`demo/runtime/*`, `demo.runner`, the backend) imports no Rumi; the server launcher's preflight (`integration/serve.py`) does import `rumi` and `rumi._core` once, only to verify they come from `Rumi\src`.

## Recovery API (`agent/recovery.py`, `agent/agent.py`)
Case: the process died after a tool acted but before its result was saved, so history ends with an unanswered `ToolRequestIdea`.
- `agent.pending_tool_calls()` returns a **list**: `[]` or `[{request_idea_id, tool_call_id, tool_name, arguments}]` (one dict inside the list). Read-only: no model call, no tool run, no write. Unsupported shapes raise `UnsupportedRecoveryError` (`.reason`, `.calls`).
- `agent.record_recovered_result(request_idea_id, tool_call_id, result)` saves a caller-confirmed result without running the tool. `result` is a `str` (verbatim) or a JSON-compatible value (stored via `json.dumps`; NaN and non-JSON types are rejected). It returns the `ToolResultIdea` with the original `tool_call_id`, the tool name from the request, and `metadata == {"recovered": True}`.
- Repeating an equal result (same text, or equal canonical JSON; `1`, `1.0`, `true` are distinct) returns the saved idea and writes nothing, even from a new process. A different result raises `RecoveryConflictError` and changes nothing. Unknown ids raise `ToolCallNotFoundError`.
- `agent.whirl(...)` raises `RecoveryNeededError` (`.pending`, `.reason`, `.recoverable`) while a call is unfinished, before saving input or calling the model.
- Supported shape: exactly one unfinished call, inside a request with exactly one call, and that request is the last idea. Other shapes give `UnsupportedRecoveryError.reason` in: `multiple_unfinished_requests, multi_call_request, history_continues, invalid_tool_call, duplicate_results, stale_history`. Do not repair them by appending ideas.
- Rumi never decides whether the external effect happened; the caller verifies it. This console records a result only when the SQLite ledger has exactly one row matching the original request. Absent, duplicate or mismatched rows stay unresolved; never invent an "error / not charged" result.

## Real crash fixture
`Rumi/tests/recovery_agent.py` and `tests/test_recovery.py`: a tool commits a SQLite row, then `os._exit(17)` (no exception, no cleanup, no result saved). Phases (crash, inspect, record, whirl) run in fresh interpreters. The model is mocked by patching `rumi.heart.openrouter.OpenRouterHeart.call`; no network or API key is needed. The demo mirrors this in `demo/cashier.py` and `demo/workers/phases.py`.

## Environment and commands
Use the existing venv, `Rumi\.venv\Scripts\python.exe` (Python 3.14). Bare system `python` can import a different `rumi` (an older copy elsewhere without recovery). Do not use `python -I` for children (it drops `PYTHONPATH`).

From the repository root:
```powershell
.\Rumi\.venv\Scripts\python.exe -m integration.serve          # console at http://127.0.0.1:8765/
.\Rumi\.venv\Scripts\python.exe -m integration.test_flow      # isolated end-to-end checks (temp storage)
.\Rumi\.venv\Scripts\python.exe -m pytest -c .\Rumi\pyproject.toml .\Rumi\tests\test_recovery.py -q -p no:cacheprovider
git -C .\Rumi status --short                                  # list local changes; do not reset them
```
From `Rumi\` (library checks only):
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_recovery.py -q -p no:cacheprovider
```
Do not start a second server on 8765 and do not touch `.rumi-console/`.

## Where to look
`src/rumi/agent/recovery.py` (the module docstring is the spec) -> `agent/agent.py` (`whirl`, `pending_tool_calls`, `record_recovered_result`) -> `agent/registry.py`, `world.py`, `tablet/filesystem.py` -> `tests/test_recovery.py`. App side: `README.md`, `context/SPEC.md`, `demo/runtime/contract.py` (identity constants).
