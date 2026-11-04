# Cloudflare hosting

Public console: https://mineai.net/recovery-agent/ (the bare path redirects here).

Cloudflare serves the existing frontend assets. Only `/recovery-agent/api/*` is
bridged to a Workers VPC Service, through the dedicated `rumi-recovery-agent-pc`
tunnel, to `127.0.0.1:8766` on the host computer. The service binding fixes that
single target; the Worker has no general private-network binding. Other site
paths continue to the existing origin. No DNS records were changed.

## Keep it running on this Windows computer

The host has an on-demand, limited-user scheduled task. Start it after a reboot
or if the connection is down; it has no automatic login/startup trigger:

```powershell
Start-ScheduledTask -TaskName RumiRecoveryConsoleHosting
.\Rumi\.venv\Scripts\python.exe -m integration.hosting status
```

The task runs `Rumi/.venv/Scripts/pythonw.exe -m integration.hosting run`, with the
repository root as its working directory and no execution time limit. This keeps
the hidden Python server and QUIC tunnel outside the chat application's process
tree. Keep the computer awake, online, and signed in. No Windows service is installed.
`status` never starts or stops anything. PID ownership includes creation time and
executable identity; a foreign listener is refused rather than replaced. The
launcher never kills a process. `start` remains available for manual use; `run`
supervises the same processes, exits if either dies, and does not restart them.

Runtime files stay outside the repository under `%USERPROFILE%/.rumi-recovery-host/`.
This path avoids AppData virtualization between desktop apps and Task Scheduler:

- `public-data/`: the public demo's isolated storage root.
- `cloudflare/recovery-agent.token`: private tunnel credential; never commit or print it.
- `logs/backend.log`, `logs/tunnel.log`, `logs/supervisor.log`: process logs.
- `hosting-state.json`: process ownership metadata.

The original local console on port 8765 and its walkthrough storage are untouched.
The public demo is shared: all visitors see and operate the same active public run.
If the computer/tunnel is offline, the page still loads and reports an unavailable API.

## Files and policies

- `worker.mjs`: path redirect, three asset mappings, bounded API bridge and error handling.
- `wrangler.jsonc`: this deployment's route, assets, VPC service and rate-limit bindings.
- `worker.test.mjs`: route, framing, body limit, refusal, offline and site-preservation checks.
- `__init__.py`, `__main__.py`: Windows background launcher and ownership/readiness checks.
- `frontend/.assetsignore`: excludes Markdown instructions from static upload.

The edge forwards at most 4096 body bytes and buffers POST data into fixed-length
bytes; the Python API refuses chunked transfer. Browser cookies/Authorization are
not sent to the local demo. Cross-origin POSTs are refused, and API traffic is
limited to 30 requests per minute per client at each Cloudflare location. No POST
is automatically retried. Dynamic responses are not cached.

## Change and deploy

Use an existing authorized Wrangler login. These IDs are not credentials, but a
different account requires its own tunnel/service and updated configuration. A
fresh host needs cloudflared 2025.7.0 or newer, the private connector token file,
and outbound QUIC connectivity. Workers VPC is currently beta.

```powershell
node --test integration/hosting/worker.test.mjs
npx wrangler deploy --config integration/hosting/wrangler.jsonc --dry-run
npx wrangler deploy --config integration/hosting/wrangler.jsonc
```

After deployment, check the public page, crash (1/0/1), recover (1/1/0), repeat
recovery with the same result ID, refresh, and an ordinary site path. Run the
existing isolated complete flow if changing the backend/runner. Preserve the
dependency checkout and both local/public datasets.

References: [VPC service bindings](https://developers.cloudflare.com/workers-vpc/configuration/vpc-services/),
[tunnel requirements](https://developers.cloudflare.com/workers-vpc/configuration/tunnel/),
[static assets](https://developers.cloudflare.com/workers/static-assets/binding/),
and [rate limits](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/).
