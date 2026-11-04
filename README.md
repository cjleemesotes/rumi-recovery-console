# Rumi recovery console

A local console for one interrupted demo payment: a worker commits a SQLite row and exits before Rumi saves the tool result. Recovery verifies the existing row, saves the confirmation through Rumi, and inspects it in a fresh process.

## First checkout

Rumi is a pinned submodule from [cjleemesotes/Rumi](https://github.com/cjleemesotes/Rumi). Clone both repositories:

```powershell
git clone --recurse-submodules https://github.com/cjleemesotes/rumi-recovery-console.git
cd rumi-recovery-console
```

For an existing clone, run `git submodule update --init --recursive`.

On a new machine, install Python 3.11 or newer and a Rust toolchain (Rumi includes a native extension), then create the environment once:

```powershell
python -m venv Rumi/.venv
.\Rumi\.venv\Scripts\python.exe -m pip install -e "./Rumi[test]"
```

On Linux/macOS, use `Rumi/.venv/bin/python` instead of the Windows executable in the commands below. The existing prepared workspace already has its environment and compiled extension. No live model key is required.

## Run

From this workspace root in PowerShell:

```powershell
.\Rumi\.venv\Scripts\python.exe -m integration.serve
```

Open [the console](http://127.0.0.1:8765/). One Python server serves both the page and API. The existing Rumi environment is used; no frontend build step is required.

## Hosted demo

[mineai.net/recovery-agent](https://mineai.net/recovery-agent/) serves the frontend on Cloudflare and connects the API to a dedicated instance on the host PC. The PC must stay awake and online. Hosting uses separate shared demo data; the original local walkthrough is preserved. See [hosting instructions](integration/hosting/README.md) for the background start/status commands and deployment details.

## Where code belongs

```text
frontend/
  index.html                  Page structure
  assets/js/console.js        Browser requests, state and rendering
  assets/css/console.css      Styling
backend/
  server.py                   Stable make_server/serve entrypoint
  http/server.py              Server binding and lifecycle
  http/request_handler.py     HTTP routes, validation and static files
demo/
  cashier.py                  Stable Cashier class and payment tool identity
  runner.py                   Stable API used by the backend
  worker.py                   Stable subprocess command entrypoint
  runtime/                    Parent-side storage, processes, state and orchestration
  workers/                    Child-side ledger, history and recovery phases
integration/
  serve.py                    Startup and import preflight
  workspace.py                Code-root and import-path configuration
  test_flow.py                Stable complete-flow check command
  checks/                     Shared helpers and grouped test scenarios
Rumi/                         Existing dependency checkout
context/                      Shared specification, verified facts and worker reports
plan/                         Agreed implementation plan and completion record
```

Each code folder has a README with the detailed module map. The browser URLs `/app.js` and `/styles.css` remain stable; the backend maps them to the files under `frontend/assets/`.

## Check the complete flow

```powershell
.\Rumi\.venv\Scripts\python.exe -m integration.test_flow --keep
```

Checks use temporary storage and another loopback port. They cover the real crash, fresh inspection, recovery, repeat recovery, restart, run isolation, and refusal cases. See [integration/README.md](integration/README.md) for options.

## Interfaces and saved data

- Public entrypoints stay at `backend.server`, `demo.runner`, `demo.worker`, `integration.serve`, and `integration.test_flow`.
- `demo.cashier.Cashier` remains defined in `demo/cashier.py`; its qualified name is part of saved agent identity.
- Runtime data lives under `.rumi-console/`, separately from source and the dependency's `Rumi/data/`. Each run has its own SQLite database and Rumi history.
- The [specification](context/SPEC.md) defines the HTTP and State contracts. [Context and naming guidance](context/CONTEXT.md) explain identity, paths, and verification history.

## Extending the code

Coding agents should start with [CLAUDE.md](CLAUDE.md), then the guide in the folder they will work on. The [Rumi dependency guide](context/RUMI_GUIDE.md) explains the library without adding files to its preserved checkout.

- Put shared demo identity, storage paths, worker phases, timing policies and strict payment checks in `demo/runtime/contract.py`. Add error definitions there once; message, HTTP status and screen-phase maps are derived from the catalogue.
- Keep parent orchestration separate from worker execution. The parent imports no Rumi agent code; each inspection and recovery opens its own process. A recovery worker's response needs confirmation by a separate inspection.
- Keep integration expectations independent of application constants. The checks must detect a wrong identity, storage path or API value rather than reproduce it.
- The small public facade modules are intentional compatibility boundaries. Preserve them and the `demo.cashier.Cashier` definition when moving internal code.
