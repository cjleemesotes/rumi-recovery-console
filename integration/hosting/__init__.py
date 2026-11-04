"""Local Windows hosting launcher: the PUBLIC console (127.0.0.1:8766) plus its Cloudflare Tunnel.

    .\\Rumi\\.venv\\Scripts\\python.exe -m integration.hosting start    # start or reuse both, hidden
    .\\Rumi\\.venv\\Scripts\\python.exe -m integration.hosting status   # report only; never starts or stops
    .\\Rumi\\.venv\\Scripts\\pythonw.exe -m integration.hosting run     # start, then stay alive while both live

`run` is a foreground supervisor for an on-demand scheduled task: it calls `start`, then
checks every 30 s that the recorded backend and tunnel are still ours and alive. It exits 1
when either is gone (it never restarts or kills anything) and 0 on Ctrl+C. Under pythonw.exe
its output goes to logs\\supervisor.log.

Everything runtime lives under the user's ~/.rumi-recovery-host (outside the repo):
public-data\\ (isolated --storage-root), logs\\, hosting-state.json (PID metadata), and the
coordinator-created cloudflare\\recovery-agent.token (only its existence is checked; it is never read).

Ownership is by PID *and* process creation time *and* executable path, so a reused PID is never
mistaken for ours. There is deliberately no stop command: this launcher never kills anything.
The product console on 127.0.0.1:8765, its storage, and any other cloudflared are never touched.
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from integration.workspace import CODE_ROOT, DEFAULT_PORT, LOOPBACK_HOST

__all__ = ["APP_DIR", "PUBLIC_PORT", "main", "run", "start", "status"]

PUBLIC_PORT = 8766
TUNNEL_METRICS_PORT = 20266          # cloudflared /ready endpoint; outside its default 20241-20245 range
# AppData can be virtualized inside desktop apps. The user profile path is shared
# with Task Scheduler, so its supervisor and an interactive status command agree.
APP_DIR = Path.home() / ".rumi-recovery-host"
PUBLIC_STORAGE_ROOT = APP_DIR / "public-data"
TOKEN_FILE = APP_DIR / "cloudflare" / "recovery-agent.token"
LOG_DIR = APP_DIR / "logs"
STATE_FILE = APP_DIR / "hosting-state.json"
DEFAULT_CLOUDFLARED = Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe")
BACKEND_READY_TIMEOUT_SECONDS = 30   # preflight + bind on a cold interpreter
TUNNEL_READY_TIMEOUT_SECONDS = 20    # first edge connection
POLL_INTERVAL_SECONDS = 0.5
HEALTH_PROBE_TIMEOUT_SECONDS = 3
SUPERVISE_INTERVAL_SECONDS = 30      # `run`: how often the supervisor confirms both processes are alive

# Hidden console, own process group, and (when the caller's job allows it) outside the caller's
# job object, so the children survive the launcher's terminal closing.
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000

assert PUBLIC_PORT != DEFAULT_PORT, "the public instance must never use the product port"


# ---------------------------------------------------------------- process identity (read-only)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259


def process_identity(pid: int) -> dict | None:
    """{"pid", "created", "image"} for a LIVE process, else None. Opens a query-only handle."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) or exit_code.value != STILL_ACTIVE:
            return None
        created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        if not kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                        ctypes.byref(kernel_time), ctypes.byref(user_time)):
            return None
        image = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(image))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
            return None
        return {"pid": pid, "created": (created.dwHighDateTime << 32) | created.dwLowDateTime,
                "image": image.value}
    finally:
        kernel32.CloseHandle(handle)


def is_owned_and_alive(record: dict | None) -> bool:
    """True only if the recorded PID is alive AND has the recorded creation time and image."""
    if not record or not isinstance(record.get("pid"), int):
        return False
    current = process_identity(record["pid"])
    return (current is not None and current["created"] == record.get("created")
            and os.path.normcase(current["image"]) == os.path.normcase(str(record.get("image", ""))))


# ---------------------------------------------------------------- state, probes, commands

def load_state() -> dict:
    try:
        state = json.loads(STATE_FILE.read_text("utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}  # a missing or corrupt record just means "nothing is known to be ours"


def save_state(state: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), "utf-8")
    os.replace(temporary, STATE_FILE)


def port_accepts_connections(port: int) -> bool:
    try:
        with socket.create_connection((LOOPBACK_HOST, port), timeout=HEALTH_PROBE_TIMEOUT_SECONDS):
            return True
    except OSError:
        return False


def http_status(url: str) -> int | None:
    """GET status code, or None when nothing answered (never raises)."""
    try:
        with urllib.request.urlopen(url, timeout=HEALTH_PROBE_TIMEOUT_SECONDS) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (OSError, ValueError):
        return None


def backend_healthy() -> bool:
    # GET / is the static page: cheap, and unlike /api/state it never spawns an inspect child.
    return http_status(f"http://{LOOPBACK_HOST}:{PUBLIC_PORT}/") == 200


def tunnel_ready() -> bool:
    return http_status(f"http://{LOOPBACK_HOST}:{TUNNEL_METRICS_PORT}/ready") == 200


def find_cloudflared() -> Path | None:
    found = shutil.which("cloudflared")
    if found:
        return Path(found)
    return DEFAULT_CLOUDFLARED if DEFAULT_CLOUDFLARED.is_file() else None


def console_python() -> str:
    """The console interpreter, even when this launcher runs under pythonw.exe.

    The backend must be a console process (hidden by CREATE_NO_WINDOW): its demo worker children
    are console programs, and under a windowless pythonw parent each one would open a new window.
    """
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe" and (executable.parent / "python.exe").is_file():
        return str(executable.parent / "python.exe")
    return sys.executable


def backend_command() -> list[str]:
    return [console_python(), "-m", "integration.serve",
            "--port", str(PUBLIC_PORT), "--storage-root", str(PUBLIC_STORAGE_ROOT)]


def tunnel_command(cloudflared: Path) -> list[str]:
    return [str(cloudflared), "tunnel", "--no-autoupdate", "--protocol", "quic",
            "--metrics", f"{LOOPBACK_HOST}:{TUNNEL_METRICS_PORT}",
            "run", "--token-file", str(TOKEN_FILE)]


def spawn_hidden(name: str, command: list[str], cwd: Path) -> dict:
    """Start one detached, windowless child with its output appended to logs\\<name>.log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    with open(log_path, "ab") as log_file:
        log_file.write(f"\n=== {datetime.now(timezone.utc).isoformat()} start {name} ===\n".encode())
        log_file.flush()
        flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        try:
            process = subprocess.Popen(command, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=log_file,
                                       stderr=subprocess.STDOUT, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB)
        except PermissionError:  # the caller's job forbids breakaway; start inside it instead
            process = subprocess.Popen(command, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=log_file,
                                       stderr=subprocess.STDOUT, creationflags=flags)
    identity = process_identity(process.pid) or {"pid": process.pid, "created": None, "image": command[0]}
    return {**identity, "command": command, "log": str(log_path),
            "started_utc": datetime.now(timezone.utc).isoformat()}


def wait_until(predicate, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(POLL_INTERVAL_SECONDS)
    return predicate()


def describe(state: dict) -> dict:
    backend, tunnel = state.get("backend"), state.get("tunnel")
    return {
        "backend": {"owned_and_alive": is_owned_and_alive(backend), "pid": (backend or {}).get("pid"),
                    "url": f"http://{LOOPBACK_HOST}:{PUBLIC_PORT}/", "healthy": backend_healthy(),
                    "storage_root": str(PUBLIC_STORAGE_ROOT)},
        "tunnel": {"owned_and_alive": is_owned_and_alive(tunnel), "pid": (tunnel or {}).get("pid"),
                   "ready": tunnel_ready(), "token_file_present": TOKEN_FILE.is_file()},
        "logs": str(LOG_DIR), "state_file": str(STATE_FILE),
    }


def start() -> int:
    state = load_state()
    PUBLIC_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    if is_owned_and_alive(state.get("backend")):
        if not backend_healthy():
            print(f"REFUSED: our backend (pid {state['backend']['pid']}) is alive but not answering on "
                  f"{PUBLIC_PORT}; not starting a second one. See {LOG_DIR}.", file=sys.stderr)
            return 1
        print(f"backend: reusing healthy pid {state['backend']['pid']}")
    elif port_accepts_connections(PUBLIC_PORT):
        print(f"REFUSED: {LOOPBACK_HOST}:{PUBLIC_PORT} is in use by a process this launcher did not start.",
              file=sys.stderr)
        return 1
    else:
        state["backend"] = spawn_hidden("backend", backend_command(), CODE_ROOT)
        save_state(state)
        if not wait_until(backend_healthy, BACKEND_READY_TIMEOUT_SECONDS):
            print(f"backend started (pid {state['backend']['pid']}) but not healthy yet; see {LOG_DIR}",
                  file=sys.stderr)
            return 1
        print(f"backend: started pid {state['backend']['pid']} on {LOOPBACK_HOST}:{PUBLIC_PORT}")

    if is_owned_and_alive(state.get("tunnel")):
        print(f"tunnel: reusing pid {state['tunnel']['pid']}")
    else:
        cloudflared = find_cloudflared()
        if not TOKEN_FILE.is_file():
            print(f"REFUSED: tunnel not started; token file not found at {TOKEN_FILE}.", file=sys.stderr)
            return 1
        if cloudflared is None:
            print("REFUSED: tunnel not started; cloudflared.exe not found.", file=sys.stderr)
            return 1
        state["tunnel"] = spawn_hidden("tunnel", tunnel_command(cloudflared), APP_DIR)
        save_state(state)
        print(f"tunnel: started pid {state['tunnel']['pid']}")
    if not wait_until(tunnel_ready, TUNNEL_READY_TIMEOUT_SECONDS):
        print(f"tunnel not ready yet (no edge connection on /ready); see {LOG_DIR}", file=sys.stderr)
        return 1
    print("tunnel: ready")
    return 0


def status() -> int:
    report = describe(load_state())
    print(json.dumps(report, indent=2))
    all_up = (report["backend"]["owned_and_alive"] and report["backend"]["healthy"]
              and report["tunnel"]["owned_and_alive"] and report["tunnel"]["ready"])
    return 0 if all_up else 1


def _send_output_to_supervisor_log_if_windowless() -> None:
    """pythonw.exe has no stdout/stderr (both None); keep the supervisor's messages in a log."""
    if sys.stdout is None or sys.stderr is None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = open(LOG_DIR / "supervisor.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115 — lives for the process
        sys.stdout = sys.stdout or log_file
        sys.stderr = sys.stderr or log_file


def run() -> int:
    """Start (or reuse) both processes, then stay alive while both remain ours and alive."""
    _send_output_to_supervisor_log_if_windowless()
    print(f"=== {datetime.now(timezone.utc).isoformat()} supervisor pid {os.getpid()} ===", flush=True)
    started = start()
    if started != 0:
        print(f"supervisor: start failed (exit {started}); not supervising", file=sys.stderr, flush=True)
        return started
    watched = {name: load_state().get(name) for name in ("backend", "tunnel")}
    print(f"supervisor: watching backend pid {watched['backend']['pid']} and tunnel pid {watched['tunnel']['pid']}",
          flush=True)
    try:
        while True:
            for name, record in watched.items():
                if not is_owned_and_alive(record):
                    print(f"{datetime.now(timezone.utc).isoformat()} supervisor: {name} pid {record['pid']} "
                          "is no longer running; exiting (no restart)", file=sys.stderr, flush=True)
                    return 1
            time.sleep(SUPERVISE_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("supervisor: interrupted; leaving both processes running", flush=True)
        return 0


def main(argv: list[str]) -> int:
    if os.name != "nt":
        print("integration.hosting supports Windows only.", file=sys.stderr)
        return 2
    command = argv[0] if argv else ""
    if command == "start":
        return start()
    if command == "status":
        return status()
    if command == "run":
        return run()
    print("usage: python -m integration.hosting start|status|run", file=sys.stderr)
    return 2
