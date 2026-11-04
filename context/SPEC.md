# Rumi recovery console specification

Final v1, consolidated after one bounded worker review including the Opus complete-flow review. Coordinator owns changes. The recording gate was satisfied by START on November 4, 2026; this specification is implemented and verified. See CONTEXT.md for the completion record.

## Product and exact flow

One local page titled **Rumi recovery demo**, visibly labeled **Deterministic model response; real process crash, SQLite write, and recovery**. Two main buttons, always labeled **Run crash demo** and **Recover result**. No chat, real payments, model selection, account setup, multi-tool repair, arbitrary agent history, or model continuation after recovery.

The three evidence panels are **What the agent requested**, **What actually happened**, and **What Rumi saved**. Identifiers and diagnostic details remain readable and visually secondary, as confirmed by the user's implementation instructions.

1. Page loads the current run, or an idle view.
2. Run crash demo allocates a new isolated run. A deterministic Rumi whirl calls record_payment for A-1 / 42. The tool really commits one SQLite record and its child process exits 17 before returning. This is the expected interruption, not an HTTP error.
3. Fresh inspection displays the persisted pending request (including both original identifiers), the one committed database row, exit code 17, and counters **1 record / 0 saved results / 1 pending call**.
4. Recover result verifies the external row against the ORIGINAL stored request, then calls Rumi's recovery API without invoking record_payment or the model.
5. A DIFFERENT fresh inspection process must find the confirmed recovered ToolResultIdea persisted in Rumi, exactly one ledger row, exactly one result for the request/call, and zero pending calls. Only then show **Recovered** and counters **1 / 1 / 0**.
6. Repeating Recover result verifies the evidence again, records the same result through the API, and retains the same result idea ID and counters. Run crash demo always creates a new run and preserves earlier runs on disk.

## Screen states

| State | Evidence/message | Run button | Recover button |
|---|---|---|---|
| idle | No demo yet; counters 0/0/0 | enabled | disabled |
| running (client only) | Creating record and interrupting worker | disabled | disabled |
| pending | Worker exited 17; request + row visible; 1/0/1 | enabled | enabled |
| recovering (client only) | Checking SQLite and saving confirmed result | disabled | disabled |
| recovered | Persisted result + fresh no-pending verification; 1/1/0 | enabled | enabled; helper “Safe to repeat” |
| unresolved | Evidence absent, ambiguous, mismatched, or unavailable; show reason and preserved facts | enabled | enabled if original request is supported |
| unsupported | Rumi rejected the history shape; show reason; no repair | enabled | disabled |
| error | Startup/worker/storage/transport failure; never imply success | enabled when no request in flight | disabled until a fresh state establishes a supported request |

Display run ID, original tool name and decoded arguments, request_idea_id, tool_call_id, ledger rows/count, saved result ID/content and recovered flag, three counters, and a plain-language reason when blocked. Preserve request details after recovery even though pending_calls becomes empty. Render values as text. Frontend sends relative URLs; no second origin/build step. On page refresh call GET /api/state. On uncertain/failed POST, inspect state before suggesting retry; do not automatically repeat a new-run POST.

## Run identity, storage, and import invariants

- CODE_ROOT = absolute package parent (parent of integration/ and demo/), independent of shell cwd. STORAGE_ROOT defaults to CODE_ROOT; launcher checks may select an isolated temporary STORAGE_ROOT. Code imports/static files never move with storage. Run ID = server-generated `uuid.uuid4().hex`, accepted in URLs only as `^[0-9a-f]{32}$`. Client never supplies a filesystem path or result.
- Store STORAGE_ROOT/.rumi-console/active.json with active run ID, and STORAGE_ROOT/.rumi-console/runs/<run_id>/run.json, ledger.sqlite3, rumi/. Each click uses a new directory/database. No deletion/reset endpoint or existing-data reuse.
- Durable run.json version 1 contains run_id, agent_type `demo.cashier.Cashier`, agent_id `till-1`, tool_call_id `call_pay_1`, expected tool/arguments, observed crash exit code, and the original request_idea_id once observed. Use atomic UTF-8 JSON replacement. Paths are derived from the validated run ID beneath the root, not accepted from a request.
- The original request lives in Rumi history. After crash, inspect it and retain its generated request_idea_id in run.json BEFORE recovery. The UUID in examples below is illustrative, never hardcode it. Repeat recovery uses retained request_idea_id + tool_call_id even when pending_calls is empty; validate them against the actual persisted ToolRequestIdea.
- If startup was interrupted before request identity was copied into run.json, a fresh inspect may discover it only from the single supported original stored demo request; recover must persist that exact identity before recording. Missing/contradictory metadata or unknown history must not be guessed into success. active.json survives ordinary server restarts; inspection reopens the recorded run rather than trusting an in-memory registry.
- Define Cashier ONLY in importable `demo/cashier.py`; all phases import `demo.cashier.Cashier`. Never run that file directly or define the class in a `-m` entry module. Explicit agent ID and exact absolute tablet/db paths are shared by all phases.
- Launcher selects the existing CODE_ROOT/Rumi/src checkout. Children use the SAME sys.executable, cwd=CODE_ROOT, PYTHONPATH=CODE_ROOT + CODE_ROOT/Rumi/src + any needed existing entries (platform path separator), `-X utf8`, and child-only RECOVERY_LEDGER/RECOVERY_CRASH_AFTER_COMMIT plus RUMI_CONSOLE_STORAGE_ROOT. Clear the crash flag outside crash phase. No server-global environment mutation, network model call, or library registry reset. Never substitute a temporary storage path into imports or child cwd.

## Backend ↔ demo Python handoff

`demo.runner` exports `start_run(storage_root: Path) -> dict`, `current_state(storage_root: Path) -> dict`, `inspect_run(storage_root: Path, run_id: str) -> dict`, `recover_run(storage_root: Path, run_id: str) -> dict`. This argument selects STORAGE_ROOT only; runner derives CODE_ROOT from its own package location. Returned dict is the State schema below. `DemoError` has code, message, http_status, and optional state (a fresh State when available). Backend returns DemoError.state unchanged at its http_status; the runner sets that State's error field. Without state, backend returns the error-only envelope. Unexpected exceptions/non-dict returns map to 500 internal_error, with traceback on stderr only.

These module paths remain stable entrypoints after the organization cleanup: demo.runner delegates to demo.runtime, demo.worker dispatches demo.workers phases, and backend.server delegates to backend.http. Cashier is still defined in demo.cashier. Browser `/app.js` and `/styles.css` now read frontend/assets/js/console.js and frontend/assets/css/console.css through the backend's explicit static map. The root/folder READMEs describe the current source layout; this interface contract is unchanged.

Backend imports those functions; demo.runner owns storage, SQLite confirmation, subprocess calls, and snapshot assembly. Backend owns HTTP/status mapping and static files, never duplicates recovery logic. Single-process, single-threaded `HTTPServer` serializes all operations; no reloader or multiple server workers. Child command is `[sys.executable, '-X', 'utf8', '-m', 'demo.worker', phase, absolute_run_dir]`, phase = crash | inspect | recover. Entry module imports the Cashier class. Expected crash exit =17 with no JSON; other successful phases exit 0 with one JSON object on stdout, logs on stderr. Bound each child to 15 seconds; kill/reap timed-out children and inspect rather than declaring recovery success. Recovery success always requires a subsequent independent inspect child.

The parent runner creates the database with the UNCHANGED fixture table `payments(order_id TEXT NOT NULL, amount INTEGER NOT NULL)` before launching crash, and atomically persists manifest/active-run identity. The recover CHILD owns fresh World construction, original-request validation, read-only ledger confirmation, and the actual Rumi recovery call in the SAME child; refused domain outcomes return exit0 plus JSON for the parent to translate. Parent runner never constructs a World/Cashier or invokes a tool; launcher may import rumi/_core for preflight only. Child checks RUMI_CONSOLE_STORAGE_ROOT and validates that run_dir resolves to its .rumi-console/runs/<32hex>, then derives both storage paths itself. Build the read-only SQLite URI with `Path.resolve().as_uri() + '?mode=ro'`, uri=True; fetch all rows ordered by rowid before counting. Parent decodes child stdout explicitly as UTF-8.

Windows timeout cleanup must leave no worker interpreter alive: the venv python.exe launches a different interpreter PID. Integration verified that subprocess.run(timeout=...) kills/reaps successfully on this host with no orphan or pipe hang; use that supported path. If using manual Popen instead, terminate its entire still-owned process tree before waiting (bounded taskkill /T /F is available). Never kill unrelated Python/Claude processes. Atomic manifest replacement may retry PermissionError briefly, then report storage_failed rather than hiding failure.

## HTTP agreement

Base `http://127.0.0.1:8765`. GET / serves frontend/index.html; /app.js and /styles.css serve frontend assets. JSON APIs use UTF-8 and `Cache-Control: no-store`. No framework, frontend dev server, CORS, pip install, or Rust rebuild is required. A second bind fails clearly rather than taking another address silently.

Backend entry points: `make_server(root: Path, host: str = '127.0.0.1', port: int = 8765, *, storage_root: Path | None = None) -> HTTPServer` binds without serving; `serve(root: Path, host: str = '127.0.0.1', port: int = 8765, *, storage_root: Path | None = None) -> None` serves and closes on shutdown. Root is absolute CODE_ROOT; storage_root defaults to root and is forwarded to runner functions. Port 0 is allowed for checks and exposes server.server_address. Launcher calls serve with loopback 127.0.0.1 and accepts optional `--storage-root PATH` and `--port N` for isolated integration checks; the ordinary startup command needs no flags. Use an HTTPServer subclass with allow_reuse_address=False and, on Windows, SO_EXCLUSIVEADDRUSE set BEFORE bind. A bind failure exits nonzero naming host:port. Handler uses HTTP/1.0 (close responses) and a 5-second connection-read timeout so speculative idle browser sockets cannot indefinitely block the single server thread. No switch to threads is planned unless an observed browser blocker requires it.

Static serving is an exact allow-list `/`, `/app.js`, `/styles.css`, with text/html, text/javascript, text/css and UTF-8; use Cache-Control:no-store for all. Favicon may return a quick404. Ignore query strings for routing; trailing-slash alternatives are404. Known routes with the wrong method are405 (GET /api/runs allows POST). Reject transfer-encoded bodies; absent/zero Content-Length means `{}`; more than4096 bytes is413; malformed UTF-8/JSON, non-object, nonempty object, or invalid ID is400 with code invalid_request. Frontend treats error codes generically and displays message/reason. Do not set a browser timeout shorter than45 seconds: a POST can require two15-second children, and other requests queue behind it.

| Method/path | Request | Response |
|---|---|---|
| GET /api/state | no body | 200 State for active run, or idle State |
| POST /api/runs | `{}` | 201 pending State after expected crash and fresh inspection |
| GET /api/runs/{run_id} | no body | 200 freshly inspected State |
| POST /api/runs/{run_id}/recover | `{}` | 200 recovered State, including on repeat; 409 fresh unresolved/unsupported State with error |

POST bodies must be JSON object `{}` (accept an absent body as `{}`). Reject all supplied outcome/result/argument/path fields with 400. Invalid IDs/bad JSON ->400; unknown run/route ->404; wrong method ->405 with Allow. Infrastructure/worker failure ->502, persistence/server failure ->500; return available facts without claiming a completed step. For errors without a readable run return `{"error":{"code":"unknown_run","message":"Demo run not found."}}`; otherwise return the State with its error field set. Browser must handle both. Expected exit 17 is a successful POST /api/runs response.

State fields are fixed across all four endpoints: schema_version, demo, phase, run_id, agent, request, pending_calls, ledger, saved_result, counts, verification, error. `phase` = idle | pending | recovered | unresolved | unsupported | error. `verification.record` = not_checked | matched | absent | ambiguous | mismatched | unreadable. `fresh_inspection` refers to a new process that actually read persisted Rumi history, not an in-memory result. saved_results counts results for the ORIGINAL request/call, not every history result with a reused call ID.

Unknown evidence is explicit: ledger.rows and ledger.count may be null on read failure; pending_calls and each counts value may be null when history/count cannot be read. UI renders null as “unknown”, never zero. saved_result.result is parsed JSON when possible (any JSON type or null); content is the exact saved string and remains the display source. A recovered v1 run specifically requires the expected result OBJECT. Every non-null error is visibly displayed, even if the response also includes a State. Error-only bodies preserve the previous snapshot with an uncertainty message. After an uncertain POST or error State with a run_id, do one GET of that run; no polling or automatic POST retry.

| Condition / error.code | phase | Recover HTTP status | Writes |
|---|---|---:|---|
| record_absent / record_ambiguous / record_mismatched / record_unreadable | unresolved |409| no Rumi result |
| recovery_conflict (different existing result) | unresolved |409| existing result preserved |
| unsupported_history (including reason stale_history) | unsupported |409| no repair |
| original_request_missing / demo_identity_mismatch | unsupported |409| no repair |
| worker_timeout / worker_failed / inspection_failed (including post-save inspection failure) | error |502| completion unknown; inspect next |
| storage_failed | error |500| no claim of completed save |

GET inspection returns200 for readable pending/recovered/unresolved/unsupported states; an actual worker/storage failure retains502/500. An error State sets fresh_inspection=false if a new history read did not succeed. UI enables Recover only for pending/recovered/unresolved with a supported request. Error/unsupported disable it until a fresh inspection establishes a supported state. A successful fresh GET does not erase the visible explanation of a failed POST before the user can read it.

### Canonical examples (frontend and backend must share these)

Initial GET /api/state:

```json
{
  "schema_version": 1, "demo": true, "phase": "idle", "run_id": null,
  "agent": null, "request": null, "pending_calls": [],
  "ledger": {"rows": [], "count": 0}, "saved_result": null,
  "counts": {"records": 0, "saved_results": 0, "pending_calls": 0},
  "verification": {"record": "not_checked", "fresh_inspection": false, "worker_exit_code": null},
  "error": null
}
```

POST /api/runs `{}` ->201 (example generated IDs):

```json
{
  "schema_version": 1, "demo": true, "phase": "pending",
  "run_id": "a1111111111111111111111111111111",
  "agent": {"type": "demo.cashier.Cashier", "id": "till-1"},
  "request": {"request_idea_id": "req-example", "tool_call_id": "call_pay_1", "tool_name": "record_payment", "arguments": {"order_id": "A-1", "amount": 42}},
  "pending_calls": [{"request_idea_id": "req-example", "tool_call_id": "call_pay_1", "tool_name": "record_payment", "arguments": {"order_id": "A-1", "amount": 42}}],
  "ledger": {"rows": [{"order_id": "A-1", "amount": 42}], "count": 1},
  "saved_result": null,
  "counts": {"records": 1, "saved_results": 0, "pending_calls": 1},
  "verification": {"record": "matched", "fresh_inspection": true, "worker_exit_code": 17},
  "error": null
}
```

POST /api/runs/a1111111111111111111111111111111/recover `{}` ->200:

```json
{
  "schema_version": 1, "demo": true, "phase": "recovered",
  "run_id": "a1111111111111111111111111111111",
  "agent": {"type": "demo.cashier.Cashier", "id": "till-1"},
  "request": {"request_idea_id": "req-example", "tool_call_id": "call_pay_1", "tool_name": "record_payment", "arguments": {"order_id": "A-1", "amount": 42}},
  "pending_calls": [],
  "ledger": {"rows": [{"order_id": "A-1", "amount": 42}], "count": 1},
  "saved_result": {
    "idea_id": "result-example", "request_idea_id": "req-example", "tool_call_id": "call_pay_1", "tool_name": "record_payment",
    "content": "{\"order_id\": \"A-1\", \"amount\": 42, \"status\": \"recorded\"}",
    "result": {"order_id": "A-1", "amount": 42, "status": "recorded"}, "recovered": true
  },
  "counts": {"records": 1, "saved_results": 1, "pending_calls": 0},
  "verification": {"record": "matched", "fresh_inspection": true, "worker_exit_code": 17},
  "error": null
}
```

Repeating the POST returns the SAME recovered State and saved_result.idea_id (fresh_inspection remains true). Refreshing or restarting the server then GET also returns persisted recovered evidence. JSON key ordering is immaterial.

Unconfirmed example: take the pending example, set ledger.rows to `[]`, ledger.count and counts.records to 0, phase to unresolved, verification.record to absent, and error to `{"code":"record_absent","message":"No committed payment matches the original request; outcome remains unresolved."}`. Preserve request, pending_calls, counts.saved_results=0, counts.pending_calls=1. GET returns 200; recover returns 409 with that State and no history write. Extra rows ->record_ambiguous; one wrong row ->record_mismatched; inaccessible database ->record_unreadable with ledger={"rows":null,"count":null} and counts.records=null. Unsupported history ->phase unsupported, error.code=unsupported_history and error.reason=the Rumi reason, pending_calls=exception.calls (diagnostics), no recovery write. Counts must reflect observed evidence; unknown/unreadable counts use null rather than fabricated zero.

## Recovery verification and refusal rules

Recovery opens a fresh agent and validates the exact original ToolRequestIdea, its IDs, one tool named record_payment, and decoded args exactly `{"order_id":"A-1","amount":42}`. Require exact keys, type(order_id) is str and type(amount) is int (42.0/bool are not substitutes). Validate the retained manifest identity against that history; manifest/client copies never replace stored request evidence. Count only ToolResultIdeas contiguous immediately after this request with the matching call ID; do not import a private Rumi helper or match call IDs globally.

Read SQLite in read-only mode; never create a missing database while inspecting. Read ALL payments rows. Exactly ONE row must exist, with the same order_id and integer amount as the pending/original request. No row, more than one row (including unrelated/duplicate rows), a wrong value, or a read failure means unresolved. This console never infers that an absent record proves the tool did nothing and never saves an automatic error outcome.

Build confirmed result from the validated ROW values: `{"order_id":"A-1","amount":42,"status":"recorded"}`. Call record_recovered_result(original_request_id, original_call_id, confirmed). Do not call record_payment, whirl, or a model during recovery. Then inspect in another process: one exact recovered result immediately associated with the original request, metadata.recovered=true, matching result content, no pending calls, and still exactly one matching row. A clean history alone does not mean recovered.

On repeat, resolve the stored request via retained identifiers, reverify the row, and call the same API. A different existing result ->409 recovery_conflict, original result unchanged. Unsupported/stale history ->409 with the library reason; reconstruct on a future attempt, never append around it. If save succeeds but post-save inspection fails, report an error/unknown completion and re-inspect; do not fabricate a rollback or re-run the tool. Never treat child exit 0 by itself as proof.

## Observable completion criteria

One root startup command, one loopback address, no secrets/network model dependency. Browser fresh run shows actual child exit17 and 1/0/1; recovery shows verified persisted 1/1/0; repeat and refresh preserve the same result ID. A second new run has a different directory/database and does not change the first. Missing/duplicate/mismatched ledger and unsupported history fail closed with no new result. Rumi's existing local modifications remain intact. Complete-flow tests and browser walkthrough finish by recording minute55; no implementation occurs before the explicit signal.
