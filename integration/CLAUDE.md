# integration/: launcher and complete-flow checks

Read `../CLAUDE.md` for shared rules and `../context/SPEC.md` for the API/State contract.
This folder's README maps the modules. Run commands from the workspace root.

```powershell
.\Rumi\.venv\Scripts\python.exe -m integration.serve --check
.\Rumi\.venv\Scripts\python.exe -m integration.test_flow --keep
.\Rumi\.venv\Scripts\python.exe -m integration.test_flow --edges-only
```

Flow checks choose temporary storage and a free loopback port, then start the real launcher with --storage-root and --port. Never aim refusal checks at the product listener on 8765 or its saved data. Do not run them during a browser walkthrough. Report the actual check count and command result; the last complete source baseline had 304 checks.

## Files

- `workspace.py`: integration's code-root/import-path configuration, Rumi checkout/source paths, loopback host and default port. Resolve from package location, not shell cwd.
- `serve.py`: stable launcher and preflight. It imports Rumi/core to check their origin; find_spec locates the agent/worker without importing them. Importing backend.server also imports the pure demo.runner. No World is constructed by the parent demo runtime.
- `test_flow.py`: stable command entrypoint, delegating to checks/suite.py.
- `checks/results.py`: one shared RECORDER, record_check, record_check_or_abort and SectionAborted. Reset/mutate in place so importers keep the same object.
- `checks/expectations.py`: independent expected identity, payment, result and State fields; literal expectations are deliberate.
- `checks/storage.py`: isolated run, ledger, manifest and history read/tamper helpers.
- `checks/assertions.py`: State and on-disk evidence assertions.
- `checks/http_client.py`: HTTP/chunked calls and tracking of created runs.
- `checks/processes.py`: LauncherProcess start/wait/stop and log ownership.
- `checks/flow_scenarios.py`: startup/assets/idle, exclusive bind, crash/inspect/recover/repeat/refresh, restart, new-run isolation and Rumi preservation.
- `checks/refusal_scenarios.py`: absent/duplicate/mismatched/unreadable ledger evidence, unsupported history, false-success edges and invalid requests.
- `checks/suite.py`: section order via _run_section, temporary storage, summary and exit status.

## Rules and extension recipe

- Checks use the launcher command, HTTP/State, run files and Rumi's public FilesystemTablet/TextIdea. Do not import demo/backend internals to calculate expected answers.
- Keep expectations independent of app constants: otherwise a wrong app value validates itself.
- Tamper only with runs created inside the check's own temporary storage. Restore a manifest/history entry if later checks reuse that run.
- The code that starts a LauncherProcess owns cleanup on every failure path until it explicitly hands ownership back. suite.main must retain the live launcher for its finally block.
- Keep check labels clear and stable. A new scenario changes the count; report the number actually observed.
- Preserve Rumi's checkout/local modification. The suite captures its starting revision, status and agent.py fingerprint, then checks that they are unchanged. Clean clones and locally modified checkouts are both supported; do not add files inside Rumi/ for guidance.
- For a new case, first trace the deciding app code. Add to the appropriate scenario module; reuse _create_pending_run, storage helpers and _check_recovery_refused/_check_no_false_success where suitable. Put reusable new expected literals in expectations.py.
- --edges-only runs the false-success probes, not every ledger-refusal or ordinary happy-path check. Use the complete suite for a new ordinary refusal case.
- Run the complete flow once on settled app/check source. Documentation-only work needs fact review, not another product-flow run.
