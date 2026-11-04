# SEALED answer key v1: Haiku workspace-understanding trials

This file was written by the integration session (Opus) before any trial ran. It lives OUTSIDE the workspace, so `--restricted` trials cannot read it. Its SHA-256 is recorded in `context/worker-reports/haiku-integration.md`. Line numbers refer to the 40-file tree fingerprinted in `context/evidence/clean-code-source-hashes.json`. A citation counts as "correct" if it names the right file and lands within ±15 lines of the key, or inside the named function.

## Scoring (applies to every trial)
- Each fact F scores 2 when it is correct and cited to the CODE file named in the key, 1 when it is correct but cited only to docs/README/CLAUDE.md or uncited, and 0 when it is missing or wrong.
- Facts marked **[must]** must score at least 1.
- **PASS** requires ≥ 75% of the trial's points, every [must] fact ≥ 1, and no critical error.
- **Critical errors (auto-FAIL):**
  - recommends running checks or servers on 127.0.0.1:8765, or using the product CODE_ROOT/.rumi-console data
  - recommends editing Rumi/, or changing wire JSON keys, routes, env names, storage file names, or the identity `demo.cashier.Cashier` / `record_payment` / `till-1` / `call_pay_1`
  - says recovery may record an "ERROR"/"not charged" outcome, or re-runs `record_payment` or the model
  - cites two or more file paths that do not exist
- **INVALID trial** (fix the launcher and rerun, not scored): a returned model ID is not a Haiku ID; any tool other than Read, Glob or Grep was used; or a denied path (context/worker-reports, context/evaluations, context/evidence, or anything outside the workspace) was read successfully.

## Trial 1: frontend + HTTP (8 questions, 34 points)
- **Q1.** F1 [must] `/app.js` serves `frontend/assets/js/console.js` and `/styles.css` serves `frontend/assets/css/console.css`, from the static map in `backend/http/request_handler.py:34-37`. F2: the content types are `text/javascript; charset=utf-8` and `text/css; charset=utf-8` (same lines). F3: every response carries `Cache-Control: no-store` (`request_handler.py:69`).
- **Q2.** F1 [must] The body limit is 4096 bytes (`MAX_REQUEST_BODY_BYTES`, `request_handler.py:29`), enforced at `:148-149`, giving 413 `payload_too_large`. F2: a `Transfer-Encoding` body gives 400 `invalid_request` (`:137-138`).
- **Q3.** F1 [must] GET /api/runs returns 405 `method_not_allowed` with an `Allow` header naming POST (`request_handler.py:117`, `:127`).
- **Q4.** F1 [must] The client timeout is 60000 ms (`REQUEST_TIMEOUT_MS`, `frontend/assets/js/console.js:4`), applied with an AbortController in `requestJson` (`:63-65`). F2: the reason is that a POST can need two 15 s worker children (the comment at `:4`, and/or `demo/runtime/contract.py:55` `CHILD_TIMEOUT_SECONDS = 15`).
- **Q5.** F1 [must] After a failed or uncertain POST the page keeps the previous snapshot plus a notice, then does exactly ONE GET. For a new run that GET is `api/state` (or the new run's path if a State with an error came back); for recovery it is the targeted run. It never retries a POST. Evidence: `retainTransportNotice`, `reloadStateFrom` and `performAction` in `console.js` (around `:100-165`).
- **Q6.** F1 [must] Null evidence is rendered as the text "unknown", never 0 (`UNKNOWN_TEXT`, `console.js:7`, plus its use in the counters and evidence rendering).
- **Q7.** F1: the button hooks are `id`/`data-testid` `btn-run` and `btn-recover` (`frontend/index.html:17-18`).
- **Q8.** F1 [must] The server uses HTTP/1.0 with a 5 s connection read timeout (`CLIENT_READ_TIMEOUT_SECONDS`, `request_handler.py:31`, `:53-54`), so an idle browser socket cannot block the single server thread. F2: the bind is exclusive, with `allow_reuse_address = False` and `SO_EXCLUSIVEADDRUSE` set before bind (`backend/http/server.py:25`, `:36-38`).

## Trial 2: recovery semantics (8 questions, 30 points)
- **Q1.** F1 [must] `record_recovered_result` is called only in the recover CHILD process, `python -X utf8 -m demo.worker recover <run_dir>` (`demo/runtime/children.py:47-50`), inside `phase_recover` (`demo/workers/phases.py:88-120`, call at `:110`). F2: the parent/server never constructs the agent.
- **Q2.** F1 [must] SQLite is opened read-only (`as_uri() + "?mode=ro"`, `demo/workers/ledger.py:15`) and ALL rows are read, ordered by rowid (`:18`). F2 [must] The classification is: unreadable (rows None), absent (0 rows), ambiguous (more than 1), mismatched (1 row that is not exact), matched (`ledger.py:27-36`). Strict types come from `is_expected_arguments` (`demo/runtime/contract.py:109-117`). F3: each case maps to a `record_*` code, 409, phase unresolved (`contract.py:139-142`).
- **Q3.** F1 [must] The confirmed result is built from the ROW values, `{"order_id", "amount", "status": "recorded"}` (`phases.py:108-109`), not from the request or the client.
- **Q4.** F1 [must] Repeat is idempotent: Rumi returns the already-saved idea when the result is the same (`Rumi/src/rumi/agent/agent.py:396-397`; `_same_result` / canonical JSON in `Rumi/src/rumi/agent/recovery.py:342-350`). F2: a different result raises `RecoveryConflictError`, which demo maps to `recovery_conflict` (`phases.py:112-113`; `agent.py:398`).
- **Q5.** F1 [must] Only ToolResultIdeas contiguous immediately after the original request with call id `call_pay_1` count (`demo/workers/history.py:63-78`). Rumi uses the same positional rule (`recovery.py:245`).
- **Q6.** F1 [must] `metadata.recovered` must be literally `True` (`history.py:78`; `demo/runtime/state.py:83`). F2: a pending or recovered state whose manifest `worker_exit_code` is not 17 becomes phase `error` / `worker_failed` (`state.py:107-109`).
- **Q7.** F1 [must] Completion is proven by a NEW inspect child after the recover child. The parent does not trust the recover child's report, and after a timeout or crash it re-inspects (`demo/runtime/orchestration.py:104-126`; `phases.py:89-93` docstring).
- **Q8.** F1 [must] The identity is `AGENT_TYPE "demo.cashier.Cashier"`, `AGENT_ID "till-1"`, `CALL_ID "call_pay_1"` (`demo/runtime/contract.py:33-35`), with the class defined in `demo/cashier.py`. F2: it must never run as `__main__`, because module + class name is the Rumi tablet scope, and changing it orphans existing history.

## Trial 3: extension + verification (6 questions, 26 points)
The scenario is a single ledger row `("B-1", 42)` for the demo run.
- **Q1.** F1 [must] It is already refused as `record_mismatched`, because `classify_demo_payment_evidence` → `is_expected_arguments` fails on order_id (`demo/workers/ledger.py:36`, `demo/runtime/contract.py:109-117`). F2: recover returns 409 unresolved with no history write.
- **Q2.** F1 [must] Add the check in `integration/checks/refusal_scenarios.py`, in `check_evidence_refusals`. F2 [must] Reuse `_create_pending_run`, `execute_ledger_sql` (from `integration/checks/storage.py`) and `_check_recovery_refused(..., "unresolved", "record_mismatched", {"rows":[{"order_id":"B-1","amount":42}],"count":1}, 1)`.
- **Q3.** F1 [must] The expected values stay as independent literals in `integration/checks/expectations.py` (see its comment) and must NOT be imported from `demo.runtime.contract`. Otherwise a wrong app constant passes its own check (`contract.py:113-114` says tests keep their own literals).
- **Q4.** F1 [must] Verify from the workspace root with `.\Rumi\.venv\Scripts\python.exe -m integration.test_flow`, optionally with `--keep`. F2: it creates a temp STORAGE_ROOT and a free loopback port itself (`integration/checks/suite.py` `main`; `integration/checks/processes.py` `find_free_loopback_port`). F3: a green run's count rises from 304 by the new checks, which is +10 for one unresolved `_check_recovery_refused` call.
- **Q5.** F1 [must] It must never use port 8765 or the product `.rumi-console` data; must not edit Rumi/ (the suite asserts the agent.py SHA-256 and git status); must not change wire keys, routes, env or storage names, or the Cashier identity; and must not run during a browser walkthrough.
- **Q6.** F1: `--edges-only` runs only `check_false_success_edges` after startup (`integration/checks/suite.py` `main`).
