# Rumi recovery console: implementation and verification plan

The console is implemented. This is the ownership/dependency map for maintaining
the agreed single-scenario demo; context/SPEC.md defines the interface contract.

## Owners and editable areas

| Owner | Area | Responsibility |
| --- | --- | --- |
| frontend | frontend/ | Single page, evidence rendering, relative API calls |
| backend | backend/ | HTTP endpoints, request validation and static serving |
| demo | demo/ | Crash, fresh inspection, confirmation and recovery orchestration |
| Rumi | Existing dependency, read-only by default | API/identity guidance; narrow fixes only for demonstrated blockers |
| integration | integration/ | Launcher, independent flow checks, process/storage isolation |
| coordinator | Shared docs, integration and browser verification | Resolve interface changes; final review and walkthrough |

Keep these top-level folders. Share pure demo policy through runtime/contract.py;
use stable runner/server facades across folders. Keep tests independent of app constants.

## Startup and integration order

1. Follow README.md to clone the pinned Rumi submodule and create its Python environment.
2. From the workspace root, run `Rumi/.venv/Scripts/python.exe -m integration.serve`
   on Windows (use `Rumi/.venv/bin/python` on Linux/macOS).
3. The launcher checks import origins, binds one loopback HTTP server and serves the
   page/API together. Every child uses the same interpreter and absolute code/storage roots.
4. Integrate bottom-up: real crash + fresh inspection -> runner recovery -> HTTP
   sequence -> browser evidence/buttons -> repeat/refresh/restart and refusal checks.
5. Frontend work can run alongside backend/demo work once the SPEC examples are agreed.
   Integration stays active throughout; a child success report alone is never completion proof.

## Required completion checks

- Actual SQLite commit and process exit 17 precede saving a tool result; fresh inspection shows 1/0/1.
- Recover verifies the original request and all ledger rows without a tool/model rerun.
- A different fresh inspection proves 1 row / 1 literal recovered result / 0 pending calls.
- Repetition keeps the same result ID with no extra history or row; refresh/restart preserve it.
- Another run has isolated storage and leaves the earlier run unchanged.
- Absent, ambiguous, mismatched, unreadable or unsupported evidence records no guessed result.
- Body/result/path injection, invalid IDs and wrong methods are refused clearly.
- API and browser follow the same State examples; unknowns and uncertainty stay visible.
- The intended dependency checkout and all pre-existing local changes survive verification.
- Use temporary storage/another port for checks, then personally verify the browser.

Run `-m integration.test_flow --keep` on settled source. Run focused Rumi recovery
tests when relevant. Public CI checks fresh pinned checkouts on Windows and Linux.
Report checks actually run and any remaining limitation.

## Original recording milestones and predetermined cuts

The original build targeted one continuous recording under an hour, finishing by minute 55:

- Minute 10: real crash and fresh inspection.
- Minute 20: complete backend recovery.
- Minute 35: full browser sequence.
- Minute 45: freeze features; fix only completion/use blockers.
- Minute 55: fresh verification, final walkthrough and report complete.

If backend recovery was blocked at minute 20, pause added functionality and focus on
that connection. If browser integration was blocked at minute 35, use basic HTML over
the working API. Keep Rumi stable unless a reproducible blocker requires a narrow fix.
The initial implementation and walkthrough finished early; later maintenance and
publication occurred after the user confirmed recording had ended.
