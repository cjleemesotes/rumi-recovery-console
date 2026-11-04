# Frontend guidance (single page, vanilla JS)

Read `../CLAUDE.md` first for workspace-wide rules, saved-data identity and Rumi. The API and State contract is `../context/SPEC.md`. This file covers only `frontend/`.

## Files
- `index.html`: structure, DOM ids and `data-testid` hooks. It references the public URLs `styles.css` and `app.js`, not `assets/` paths.
- `assets/js/console.js`: one IIFE with all behavior. The backend serves it at `/app.js`.
- `assets/css/console.css`: all styling. Light/dark tokens are on `:root`. Served at `/styles.css`.
- No build step, no framework, no dependencies. Do not add any.

## DOM map (keep these; tests and the walkthrough use them)
- Buttons: `btn-run` ("Run crash demo"), `btn-recover` ("Recover result"). Text `helper` ("Safe to repeat").
- Status: `status` (section), `status-badge`, `status-text`. Error box: `error` (`hidden` when empty).
- Counters: `c-records` (labeled "database records"), `c-results`, `c-pending`; section `counts`.
- Panel bodies: `p-request` ("What the agent requested"), `p-happened` ("What actually happened"), `p-saved` ("What Rumi saved"). Footer: `run-id`.
- `data-testid` only (no id): `request`, `ledger-rows`, `saved-result` on the panel sections.

## Code map (`console.js`, in file order)
- Policy constants at the top: `REQUEST_TIMEOUT_MS`, `RECOVERABLE_PHASES`, `EXPECTED_CRASH_EXIT_CODE`, `UNKNOWN_TEXT`, `OPERATION`, `CURRENT_STATE_PATH`, `RUNS_PATH`, `runPath`, `recoverPath`.
- Module state, exactly three variables: `consoleState` (last State), `activeOperation` (null or an `OPERATION` value), `retainedNotice`.
- DOM helpers (`createElement`, `createPill`, `createPlaceholder`, ...), network (`requestJson`, `acceptResponse`, `reloadStateFrom`), actions (`loadInitialState`, `performAction`), view (`canRecover`, `currentStatus`, `render*Panel`, `renderErrorBox`, `render`).

## Rules
- Render every server value with `textContent` via `createElement`. Never use `innerHTML`.
- Requests use relative URLs with no leading slash (`api/state`, `api/runs`, `api/runs/{id}/recover`). POST body is `{}`.
- A body with `phase` and `schema_version` is a State at any HTTP status (200, 201, 409, 500, 502). A body with only `error` keeps the previous snapshot and sets `retainedNotice`.
- `null` evidence displays as "unknown", never 0. Keep `saved_result.content` as the display source and `recovered === true` strict.
- Uncertainty flow: after a transport failure, an error-only body, or an error State with a `run_id`, do exactly one GET and keep the failed POST's message visible. New run re-reads `api/state` (or the new run's id); recovery re-reads the run id captured before the POST. Never retry a POST and never poll.
- Both buttons are disabled while `activeOperation` is set. Recover is enabled only for `pending`, `recovered`, `unresolved` with a `request`.
- Do not turn every label or property name into a constant; keep constants for real policy (timeout, crash code, paths, operations).

## Edit recipes
- New status text for a phase: edit `PHASE_STATUS` (badge text, tone `ok`/`warn`/`bad`/empty, sentence). Add the phase to `RECOVERABLE_PHASES` only if Recover should work in it.
- New field in a panel: add one line in the matching `render*Panel` using `createDetailList` or `createIdentifierBlock`; guard null with `isUnknown`.
- New CSS class: add it to `console.css` and use the same name in JS or HTML together. Check with `rg` that no old name remains.
- New element id: add to `index.html`, read it via `getElementById(...)` inside `render`; never rename an existing id or `data-testid`.
- API or State changes: the frontend follows `../context/SPEC.md`. A cross-layer contract change needs coordinated spec, backend and frontend updates, and only when the user asks for it; a UI task alone does not authorize editing the SPEC or backend.

## Checks (run from the repository root)
```powershell
node --check frontend\assets\js\console.js
.\Rumi\.venv\Scripts\python.exe -m integration.test_flow --keep
.\Rumi\.venv\Scripts\python.exe -m integration.serve
```
- The last command starts the console on `http://127.0.0.1:8765/`. Do not start a second server while one is already listening. Browser checks: idle, Run crash demo (1/0/1), Recover result (1/1/0), repeat recovery (same result id), refresh, then another new run.
- `integration.test_flow` runs on temporary storage and another port. It only checks that `/`, `/app.js` and `/styles.css` are served with the right content types; it never executes the JS, so confirm the page in a browser after any UI change.
- Never edit `.rumi-console/`, `Rumi/`, or other folders for a frontend task.
