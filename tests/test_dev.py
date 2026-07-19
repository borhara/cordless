"""cordless dev: hot reload, HTTP round-trip, in-process deferred handlers."""

import json
import os
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import cordless.dev as dev
from cordless.dev import Reloader, _load_env, _local_invoke_worker, _make_handler, _start_tunnel, _wait_for_tunnel


@pytest.fixture
def bot_project(tmp_path):
    (tmp_path / "mybot.py").write_text(
        "from cordless import Cordless\n"
        "bot = Cordless()\n"
        "@bot.command('ping')\n"
        "async def ping(ctx):\n"
        "    await ctx.send('pong')\n"
    )
    sys.path.insert(0, str(tmp_path))
    yield tmp_path
    sys.path.remove(str(tmp_path))
    sys.modules.pop("mybot", None)


# --- Reloader ---


def test_defer_import_survives_no_region(monkeypatch):
    import sys

    import botocore.exceptions

    def _no_region(*a, **kw):
        raise botocore.exceptions.NoRegionError()

    monkeypatch.setattr("boto3.client", _no_region)
    sys.modules.pop("cordless.defer", None)
    try:
        import cordless.defer as defer_mod

        assert defer_mod._lambda_client is None
    finally:
        sys.modules.pop("cordless.defer", None)


def test_reloader_loads_bot(bot_project):
    reloader = Reloader("mybot:bot", str(bot_project))
    bot = reloader.get()
    assert "ping" in bot.router.commands


def test_reloader_returns_same_bot_when_unchanged(bot_project):
    reloader = Reloader("mybot:bot", str(bot_project))
    assert reloader.get() is reloader.get()


def test_reloader_reloads_on_change(bot_project):
    reloader = Reloader("mybot:bot", str(bot_project))
    first = reloader.get()

    src = bot_project / "mybot.py"
    src.write_text(src.read_text().replace("'pong'", "'PONG!'"))
    os.utime(src, (time.time() + 5, time.time() + 5))  # force a distinct mtime

    second = reloader.get()
    assert second is not first


# --- cloudflared tunnel ---


class _FakeProc:
    def __init__(self, stderr_lines):
        self.stderr = iter(stderr_lines)
        self.terminated = False

    def terminate(self):
        self.terminated = True


def test_start_tunnel_returns_none_when_cloudflared_not_installed(monkeypatch):
    monkeypatch.setattr(dev.shutil, "which", lambda name: None)
    assert _start_tunnel(8787) == (None, None)


def test_start_tunnel_extracts_url_from_stderr(monkeypatch):
    monkeypatch.setattr(dev.shutil, "which", lambda name: "/usr/local/bin/cloudflared")
    fake_proc = _FakeProc(["starting tunnel\n", "https://my-tunnel-name.trycloudflare.com\n", "other noise\n"])
    monkeypatch.setattr(dev.subprocess, "Popen", lambda *a, **kw: fake_proc)

    proc, url = _start_tunnel(8787)

    assert proc is fake_proc
    assert url == "https://my-tunnel-name.trycloudflare.com"


def test_start_tunnel_returns_none_url_when_no_match_found(monkeypatch):
    """cloudflared started but never printed a recognizable tunnel URL - the
    caller must be able to tell 'process is running, no url yet' apart from
    'cloudflared not installed' so it prints the right message either way."""
    monkeypatch.setattr(dev.shutil, "which", lambda name: "/usr/local/bin/cloudflared")
    fake_proc = _FakeProc(["some unrelated startup line\n"])
    monkeypatch.setattr(dev.subprocess, "Popen", lambda *a, **kw: fake_proc)

    proc, url = _start_tunnel(8787)

    assert proc is fake_proc
    assert url is None


def test_wait_for_tunnel_returns_true_once_reachable(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(url, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("not yet")
        return object()

    monkeypatch.setattr(dev.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(dev.time, "sleep", lambda _: None)

    assert _wait_for_tunnel("https://example.trycloudflare.com") is True
    assert calls["n"] == 3


def test_wait_for_tunnel_gives_up_after_timeout(monkeypatch):
    monkeypatch.setattr(dev.urllib.request, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(OSError("down")))
    monkeypatch.setattr(dev.time, "sleep", lambda _: None)

    ticks = iter([0, 1, 20])  # first call in the while-condition, then past the deadline
    monkeypatch.setattr(dev.time, "monotonic", lambda: next(ticks, 20))

    assert _wait_for_tunnel("https://example.trycloudflare.com", timeout=10) is False


# --- HTTP round-trip ---


@pytest.fixture
def dev_server(bot_project):
    reloader = Reloader("mybot:bot", str(bot_project))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(reloader))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_post_interaction_round_trip(dev_server):
    payload = json.dumps({"type": 2, "data": {"name": "ping"}}).encode()
    req = urllib.request.Request(dev_server, data=payload, method="POST")
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    assert body["data"]["content"] == "pong"


def test_ping_interaction_answered(dev_server):
    payload = json.dumps({"type": 1}).encode()
    req = urllib.request.Request(dev_server, data=payload, method="POST")
    with urllib.request.urlopen(req) as resp:
        assert json.loads(resp.read())["type"] == 1


def test_get_health_check(dev_server):
    with urllib.request.urlopen(dev_server) as resp:
        assert resp.status == 200


def test_post_interaction_with_files_round_trips_raw_bytes(bot_project):
    """isBase64Encoded responses (multipart file attachments) must be decoded
    back to raw bytes before hitting the socket, same as real API Gateway."""
    (bot_project / "mybot.py").write_text(
        "from cordless import Cordless\n"
        "bot = Cordless()\n"
        "@bot.command('file')\n"
        "async def file_cmd(ctx):\n"
        "    await ctx.send('here', files=[('report.pdf', b'binary-data')])\n"
    )
    reloader = Reloader("mybot:bot", str(bot_project))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(reloader))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        payload = json.dumps({"type": 2, "data": {"name": "file"}}).encode()
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type")
            body = resp.read()
        assert content_type.startswith("multipart/form-data")
        assert b"binary-data" in body
        assert b'filename="report.pdf"' in body
    finally:
        server.shutdown()
        server.server_close()


# --- in-process defer ---


def test_local_invoke_runs_worker_thread(bot_project, monkeypatch):
    import cordless.defer

    done = threading.Event()
    followups = []

    def fake_patch(app_id, token, payload):
        followups.append(payload)
        done.set()

    monkeypatch.setattr(cordless.defer, "patch_followup", fake_patch)

    (bot_project / "mybot.py").write_text(
        "from cordless import Cordless\n"
        "bot = Cordless()\n"
        "@bot.command('slow', defer=True)\n"
        "async def slow(ctx):\n"
        "    await ctx.send('done!')\n"
    )
    reloader = Reloader("mybot:bot", str(bot_project))

    invoke = _local_invoke_worker(reloader)
    invoke("whatever", {"type": 2, "data": {"name": "slow"}, "id": "1", "token": "t", "application_id": "a"})

    assert done.wait(timeout=5)
    assert followups[0]["content"] == "done!"


# --- env loading ---


def test_load_env_strips_double_quotes(tmp_path, monkeypatch):
    monkeypatch.delenv("QUOTED", raising=False)
    (tmp_path / ".env").write_text('QUOTED="my-token"\n')
    _load_env(str(tmp_path))
    assert os.environ.pop("QUOTED") == "my-token"


def test_load_env_strips_single_quotes(tmp_path, monkeypatch):
    monkeypatch.delenv("QUOTED", raising=False)
    (tmp_path / ".env").write_text("QUOTED='my-token'\n")
    _load_env(str(tmp_path))
    assert os.environ.pop("QUOTED") == "my-token"


def test_load_env_reads_toml_and_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("FROM_TOML", raising=False)
    monkeypatch.delenv("FROM_DOTENV", raising=False)
    monkeypatch.setenv("ALREADY_SET", "shell-wins")

    (tmp_path / "cordless.toml").write_text('[deploy.env]\nFROM_TOML = "a"\nALREADY_SET = "toml"\n')
    (tmp_path / ".env").write_text("FROM_DOTENV=b\n# comment\n\nALREADY_SET=dotenv\n")

    _load_env(str(tmp_path))

    assert os.environ["FROM_TOML"] == "a"
    assert os.environ["FROM_DOTENV"] == "b"
    assert os.environ["ALREADY_SET"] == "shell-wins"

    del os.environ["FROM_TOML"]
    del os.environ["FROM_DOTENV"]


def test_load_env_environment_overlay_wins_over_dot_env(tmp_path, monkeypatch):
    monkeypatch.delenv("KEY", raising=False)
    monkeypatch.delenv("BASE_ONLY", raising=False)
    (tmp_path / ".env").write_text("KEY=dev\nBASE_ONLY=base\n")
    (tmp_path / ".env.prod").write_text("KEY=prod\n")

    _load_env(str(tmp_path), "prod")

    assert os.environ.pop("KEY") == "prod"
    assert os.environ.pop("BASE_ONLY") == "base"


def test_load_env_missing_environment_file_falls_back_to_dot_env(tmp_path, monkeypatch):
    monkeypatch.delenv("KEY", raising=False)
    (tmp_path / ".env").write_text("KEY=dev\n")

    _load_env(str(tmp_path), "staging")

    assert os.environ.pop("KEY") == "dev"
