"""Local development server. Iterate on your bot without deploying.

Wraps bot.handle() in a plain HTTP server, hot-reloads your code on change,
and (when cloudflared is installed) opens a public tunnel so Discord can
reach it with real, signed interactions.
"""

import base64
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ._progress import _DIM, _GREEN, _RED, _RESET, _YELLOW, _tty
from .router import (
    APPLICATION_COMMAND,
    APPLICATION_COMMAND_AUTOCOMPLETE,
    MESSAGE_COMPONENT,
    MODAL_SUBMIT,
    PING,
    _resolve_command_key,
)

_WATCH_EXCLUDE = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", "dist", "build"}
_MAX_LOGGED_BODY = 2000  # characters; longer bodies (big modals, autocomplete choice lists) get truncated


def _describe_interaction(body):
    """A short label for the log line: `/command sub`, `button custom_id`,
    `select custom_id`, `modal custom_id`, `ping`, or the raw type number
    for anything unrecognized."""
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return "?"
    itype = payload.get("type")
    data = payload.get("data") or {}

    if itype == PING:
        return "ping"
    if itype == APPLICATION_COMMAND:
        key, _ = _resolve_command_key(data)
        return f"/{key}"
    if itype == APPLICATION_COMMAND_AUTOCOMPLETE:
        key, _ = _resolve_command_key(data)
        return f"/{key} (autocomplete)"
    if itype == MESSAGE_COMPONENT:
        kind = "button" if data.get("component_type", 2) == 2 else "select"
        return f"{kind} {data.get('custom_id')}"
    if itype == MODAL_SUBMIT:
        return f"modal {data.get('custom_id')}"
    return f"type {itype}"


def _timestamp():
    return time.strftime("%H:%M:%S")


def _status_color(status):
    if status < 300:
        return _GREEN
    if status < 500:
        return _YELLOW
    return _RED


def _pretty_body(body):
    if not body:
        return ""
    try:
        text = json.dumps(json.loads(body), indent=2)
    except (json.JSONDecodeError, TypeError):
        text = body
    if len(text) > _MAX_LOGGED_BODY:
        text = text[:_MAX_LOGGED_BODY] + f"\n… ({len(text) - _MAX_LOGGED_BODY} more chars)"
    return text


def _log_request(label, status, elapsed_ms, body, verbose=False):
    color = _status_color(status) if _tty else ""
    dim = _DIM if _tty else ""
    reset = _RESET if _tty else ""
    print(f"  {dim}{_timestamp()}{reset} → {label}  {color}{status}{reset}  {elapsed_ms:.0f}ms")
    if not verbose:
        return
    pretty = _pretty_body(body)
    if pretty:
        indented = "\n".join(f"      {line}" for line in pretty.splitlines())
        print(f"{dim}{indented}{reset}")


class Reloader:
    """Loads MODULE:ATTR and reloads it whenever a watched .py file changes."""

    def __init__(self, target, root):
        self.target = target
        self.root = os.path.abspath(root)
        self.bot = None
        self._mtimes = None
        self._lock = threading.Lock()

    def _scan(self):
        snapshot = {}
        for dirpath, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in _WATCH_EXCLUDE]
            for fname in files:
                if fname.endswith(".py"):
                    path = os.path.join(dirpath, fname)
                    try:
                        snapshot[path] = os.stat(path).st_mtime
                    except OSError:
                        pass
        return snapshot

    def _purge(self):
        for name, mod in list(sys.modules.items()):
            f = getattr(mod, "__file__", None)
            if f and os.path.abspath(f).startswith(self.root + os.sep):
                del sys.modules[name]

    def get(self):
        with self._lock:
            snapshot = self._scan()
            if self.bot is None or snapshot != self._mtimes:
                if self.bot is not None:
                    dim = _DIM if _tty else ""
                    reset = _RESET if _tty else ""
                    print(f"  {dim}{_timestamp()}{reset} ↻ reloading")
                    self._purge()
                self._mtimes = snapshot
                module_name, _, attr = self.target.partition(":")
                module = importlib.import_module(module_name)
                self.bot = getattr(module, attr)
            return self.bot


def _local_invoke_worker(reloader):
    """Stand-in for the Lambda async invoke: run the worker handler on a thread."""

    def invoke(function_name, interaction):
        from .worker import make_worker_handler

        handler = make_worker_handler(reloader.get())
        threading.Thread(target=handler, args=(interaction,), daemon=True).start()

    return invoke


def _load_env(source_dir, environment=None):
    """Export [deploy.env] from cordless.toml and any .env/.env.<environment> files, without clobbering the shell."""
    from ._env import load_dotenv
    from .deploy import load_config

    for key, value in load_config(source_dir).get("env", {}).items():
        os.environ.setdefault(key, str(value))

    load_dotenv(source_dir, environment)


def _make_handler(reloader, verbose=False):
    class DevHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"cordless dev is running \xe2\x9c\x93"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            event = {"body": body, "headers": dict(self.headers)}

            start = time.perf_counter()
            try:
                result = reloader.get().handle(event)
            except Exception as exc:
                import traceback

                traceback.print_exc()
                result = {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error": f"{type(exc).__name__}: {exc}"}),
                }
            elapsed_ms = (time.perf_counter() - start) * 1000

            body_out = result.get("body", "")
            # mirrors API Gateway's Lambda proxy integration: a base64Encoded
            # body carries binary data (e.g. multipart file attachments)
            payload = base64.b64decode(body_out) if result.get("isBase64Encoded") else body_out.encode()
            self.send_response(result["statusCode"])
            for key, value in result.get("headers", {}).items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

            _log_request(_describe_interaction(body), result["statusCode"], elapsed_ms, body, verbose=verbose)

        def log_message(self, fmt, *args):
            if self.command == "POST":
                return  # do_POST already logged a richer line above
            status = args[1] if len(args) > 1 else ""
            dim = _DIM if _tty else ""
            reset = _RESET if _tty else ""
            print(f"  {dim}{_timestamp()}{reset} → {self.command} {status}")

    return DevHandler


def _start_tunnel(port):
    """Spawn a cloudflared quick tunnel; returns (process, url) or (None, None)."""
    if not shutil.which("cloudflared"):
        return None, None

    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = None
    for line in proc.stderr:
        match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if match:
            url = match.group(0)
            break
    # keep draining stderr so cloudflared doesn't block on a full pipe
    threading.Thread(target=lambda: [None for _ in proc.stderr], daemon=True).start()
    return proc, url


def _wait_for_tunnel(url, timeout=10.0, interval=0.5):
    """cloudflared prints the quick-tunnel URL to stderr a beat before
    Cloudflare's edge actually starts routing it - hitting it (or handing
    it to Discord) right away can 502. Poll the real round trip (edge ->
    cloudflared -> our own do_GET) until it answers, so 'paste this into
    Discord' isn't printed a moment before the URL is actually live.
    Best-effort: gives up after `timeout` and lets the caller print the
    URL anyway rather than blocking dev startup indefinitely."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(interval)
    return False


def run_dev(target, port=8787, tunnel=True, source_dir=".", environment=None, verbose=False):
    source_dir = os.path.abspath(source_dir)
    sys.path.insert(0, source_dir)
    _load_env(source_dir, environment)

    # deferred handlers run in-process, no worker Lambda locally
    os.environ.setdefault("CORDLESS_WORKER_FUNCTION", "cordless-dev-local")
    from . import defer as defer_mod

    reloader = Reloader(target, source_dir)
    defer_mod.invoke_worker = _local_invoke_worker(reloader)

    bot = reloader.get()  # fail fast on import errors before binding the port

    server = ThreadingHTTPServer(("127.0.0.1", port), _make_handler(reloader, verbose))
    # start serving now, on a thread, so _wait_for_tunnel's own request
    # below has something to actually round-trip against - the socket is
    # already bound at this point, but nothing accepts from it until
    # serve_forever's loop is running
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print()
    print("  cordless dev")
    print(f"  local   http://127.0.0.1:{port}")

    tunnel_proc = None
    if tunnel:
        tunnel_proc, url = _start_tunnel(port)
        if url:
            if not _wait_for_tunnel(url):
                print()
                print("  (tunnel isn't answering yet - if Discord rejects this URL, wait a few seconds and re-save it)")
            print(f"  public  {url}")
            print()
            print("  paste the public url into your app's Interactions Endpoint URL")
        elif tunnel_proc is not None:
            print()
            print("  (tunnel failed to start - check your network connection)")
        else:
            print()
            import platform

            _sys = platform.system()
            if _sys == "Darwin":
                _hint = "brew install cloudflared"
            elif _sys == "Windows":
                _hint = "winget install Cloudflare.cloudflared"
            else:
                _hint = "https://github.com/cloudflare/cloudflared/releases/latest"
            print(f"  (install cloudflared for a public tunnel: {_hint})")
    print()

    if getattr(bot, "crons", None):
        for name in bot.crons:
            print(f"  cron    cordless cron {name}")
        print()

    print("  watching for changes (ctrl+c to stop)")
    print()

    try:
        while server_thread.is_alive():
            server_thread.join(timeout=1)
    except KeyboardInterrupt:
        print()
    finally:
        server.shutdown()
        server.server_close()
        if tunnel_proc:
            tunnel_proc.terminate()
