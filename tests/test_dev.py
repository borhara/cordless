"""cordless dev: hot reload, HTTP round-trip, in-process deferred handlers."""

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import cordless.dev as dev
from cordless.dev import Reloader, _load_env, _local_invoke_worker, _make_handler, _start_tunnel
from cordless.router import APPLICATION_COMMAND_AUTOCOMPLETE, MESSAGE_COMPONENT, MODAL_SUBMIT


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


def test_scan_skips_a_file_that_vanishes_between_walk_and_stat(bot_project, monkeypatch):
    reloader = Reloader("mybot:bot", str(bot_project))
    real_stat = os.stat

    def flaky_stat(path, *args, **kwargs):
        if str(path).endswith("mybot.py"):
            raise OSError("vanished")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(dev.os, "stat", flaky_stat)

    snapshot = reloader._scan()

    assert str(bot_project / "mybot.py") not in snapshot


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


def test_start_tunnel_shows_spinner_while_waiting(monkeypatch, capsys):
    monkeypatch.setattr(dev.shutil, "which", lambda name: "/usr/local/bin/cloudflared")
    fake_proc = _FakeProc(["https://my-tunnel-name.trycloudflare.com\n"])
    monkeypatch.setattr(dev.subprocess, "Popen", lambda *a, **kw: fake_proc)

    _start_tunnel(8787)

    assert "starting tunnel" in capsys.readouterr().out


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


@pytest.fixture
def route_bot_project(tmp_path):
    (tmp_path / "mybot.py").write_text(
        "import json\n"
        "from cordless import Cordless\n"
        "bot = Cordless()\n"
        "@bot.route('POST', '/gh/{repo}/hook')\n"
        "async def hook(event, bot):\n"
        "    return {'repo': event['pathParameters']['repo'], 'body': json.loads(event['body'])}\n"
        "@bot.route('GET', '/healthz')\n"
        "async def healthz(event, bot):\n"
        "    return 'ok'\n"
    )
    sys.path.insert(0, str(tmp_path))
    yield tmp_path
    sys.path.remove(str(tmp_path))
    sys.modules.pop("mybot", None)


@pytest.fixture
def route_dev_server(route_bot_project):
    reloader = Reloader("mybot:bot", str(route_bot_project))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(reloader))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_dev_serves_post_route_with_path_param(route_dev_server):
    req = urllib.request.Request(f"{route_dev_server}/gh/cordless/hook", data=b'{"ref": "main"}', method="POST")
    with urllib.request.urlopen(req) as resp:
        assert json.loads(resp.read()) == {"repo": "cordless", "body": {"ref": "main"}}


def test_dev_serves_get_route(route_dev_server):
    with urllib.request.urlopen(f"{route_dev_server}/healthz") as resp:
        assert resp.read() == b"ok"


def test_dev_unmatched_route_is_404(route_dev_server):
    try:
        urllib.request.urlopen(f"{route_dev_server}/nope")
        assert False, "expected 404"
    except urllib.error.HTTPError as exc:
        assert exc.code == 404


def _serve_route_bot(tmp_path, module_src):
    (tmp_path / "rbot.py").write_text(module_src)
    sys.path.insert(0, str(tmp_path))
    reloader = Reloader("rbot:bot", str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(reloader))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def cleanup():
        server.shutdown()
        server.server_close()
        sys.path.remove(str(tmp_path))
        sys.modules.pop("rbot", None)

    return f"http://127.0.0.1:{server.server_address[1]}", cleanup


def test_dev_route_gets_non_utf8_body_as_base64(tmp_path):
    url, cleanup = _serve_route_bot(
        tmp_path,
        "import base64\n"
        "from cordless import Cordless\n"
        "bot = Cordless()\n"
        "@bot.route('POST', '/raw')\n"
        "async def raw(event, bot):\n"
        "    assert event['isBase64Encoded'] is True\n"
        "    return base64.b64decode(event['body']).hex()\n",
    )
    try:
        req = urllib.request.Request(f"{url}/raw", data=b"\x80\x81\x82", method="POST")
        with urllib.request.urlopen(req) as resp:
            assert resp.read() == b"808182"
    finally:
        cleanup()


def test_dev_route_returning_proxy_dict_with_bytes_body(tmp_path):
    url, cleanup = _serve_route_bot(
        tmp_path,
        "from cordless import Cordless\n"
        "bot = Cordless()\n"
        "@bot.route('GET', '/bin')\n"
        "async def binroute(event, bot):\n"
        "    return {'statusCode': 200, 'body': b'raw-bytes'}\n",
    )
    try:
        with urllib.request.urlopen(f"{url}/bin") as resp:
            assert resp.status == 200
            assert resp.read() == b"raw-bytes"
    finally:
        cleanup()


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


class _RaisingBot:
    def handle(self, event):
        raise RuntimeError("boom")


class _RaisingReloader:
    def get(self):
        return _RaisingBot()


def test_post_interaction_handler_exception_returns_500(capsys):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(_RaisingReloader()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        req = urllib.request.Request(url, data=b"{}", method="POST")
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(req)
        assert excinfo.value.code == 500
        assert "RuntimeError" in json.loads(excinfo.value.read())["error"]
    finally:
        server.shutdown()
        server.server_close()
    assert "RuntimeError" in capsys.readouterr().err


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


# --- run_dev ---


class _FakeServer:
    """Stands in for ThreadingHTTPServer so run_dev never binds a real socket."""

    def __init__(self, address):
        self.server_address = address
        self.shutdown_called = False
        self.close_called = False

    def serve_forever(self):
        return

    def shutdown(self):
        self.shutdown_called = True

    def server_close(self):
        self.close_called = True


class _FakeThread:
    """Runs its target synchronously on start(), so the thread looks finished right away."""

    def __init__(self, target=None, daemon=None):
        self._target = target
        self._alive = True

    def start(self):
        assert self._target is not None
        self._target()
        self._alive = False

    def is_alive(self):
        return self._alive

    def join(self, timeout=None):
        return


class _InterruptingThread(_FakeThread):
    """Stays alive until joined, then raises like a real ctrl-c would mid-loop."""

    def is_alive(self):
        return True

    def join(self, timeout=None):
        raise KeyboardInterrupt


def _patch_fake_server(monkeypatch, thread_cls):
    holder = {}

    def factory(address, handler_cls):
        holder["server"] = _FakeServer(address)
        return holder["server"]

    monkeypatch.setattr(dev, "ThreadingHTTPServer", factory)
    monkeypatch.setattr(dev.threading, "Thread", thread_cls)
    return holder


@pytest.fixture
def run_dev_env(bot_project, monkeypatch):
    """run_dev leaves source_dir on sys.path and repoints defer.invoke_worker globally;
    restore both so it can't leak into other tests."""
    import cordless.defer as defer_mod

    monkeypatch.setattr(defer_mod, "invoke_worker", defer_mod.invoke_worker, raising=False)
    yield bot_project
    sys.path.remove(str(bot_project))


def test_run_dev_starts_and_shuts_down_cleanly(run_dev_env, monkeypatch, capsys):
    server_holder = _patch_fake_server(monkeypatch, _FakeThread)

    dev.run_dev("mybot:bot", port=0, tunnel=False, source_dir=str(run_dev_env))

    assert "watching for changes" in capsys.readouterr().out
    assert server_holder["server"].shutdown_called
    assert server_holder["server"].close_called


def test_run_dev_shuts_down_cleanly_on_keyboard_interrupt(run_dev_env, monkeypatch):
    server_holder = _patch_fake_server(monkeypatch, _InterruptingThread)

    dev.run_dev("mybot:bot", port=0, tunnel=False, source_dir=str(run_dev_env))

    assert server_holder["server"].shutdown_called
    assert server_holder["server"].close_called


def test_run_dev_prints_registered_crons(run_dev_env, monkeypatch, capsys):
    (run_dev_env / "mybot.py").write_text(
        "from cordless import Cordless\nbot = Cordless()\n@bot.cron('rate(1 day)')\nasync def nightly():\n    pass\n"
    )
    _patch_fake_server(monkeypatch, _FakeThread)

    dev.run_dev("mybot:bot", port=0, tunnel=False, source_dir=str(run_dev_env))

    assert "cordless cron nightly" in capsys.readouterr().out


def test_run_dev_prints_public_tunnel_url(run_dev_env, monkeypatch, capsys):
    _patch_fake_server(monkeypatch, _FakeThread)
    monkeypatch.setattr(dev, "_start_tunnel", lambda port: (_FakeProc([]), "https://my-tunnel.trycloudflare.com"))

    dev.run_dev("mybot:bot", port=0, tunnel=True, source_dir=str(run_dev_env))

    assert "https://my-tunnel.trycloudflare.com" in capsys.readouterr().out


def test_run_dev_reports_tunnel_failure(run_dev_env, monkeypatch, capsys):
    _patch_fake_server(monkeypatch, _FakeThread)
    fake_proc = _FakeProc([])
    monkeypatch.setattr(dev, "_start_tunnel", lambda port: (fake_proc, None))

    dev.run_dev("mybot:bot", port=0, tunnel=True, source_dir=str(run_dev_env))

    assert "tunnel failed to start" in capsys.readouterr().out
    assert fake_proc.terminated


def test_run_dev_hints_cloudflared_install_when_missing(run_dev_env, monkeypatch, capsys):
    _patch_fake_server(monkeypatch, _FakeThread)
    monkeypatch.setattr(dev, "_start_tunnel", lambda port: (None, None))
    monkeypatch.setattr("platform.system", lambda: "Darwin")

    dev.run_dev("mybot:bot", port=0, tunnel=True, source_dir=str(run_dev_env))

    assert "brew install cloudflared" in capsys.readouterr().out


# --- interaction description ---


def test_describe_interaction_invalid_json_returns_placeholder():
    assert dev._describe_interaction("not json") == "?"


def test_describe_interaction_autocomplete():
    body = json.dumps({"type": APPLICATION_COMMAND_AUTOCOMPLETE, "data": {"name": "ping"}})
    assert dev._describe_interaction(body) == "/ping (autocomplete)"


def test_describe_interaction_button():
    body = json.dumps({"type": MESSAGE_COMPONENT, "data": {"component_type": 2, "custom_id": "confirm"}})
    assert dev._describe_interaction(body) == "button confirm"


def test_describe_interaction_select():
    body = json.dumps({"type": MESSAGE_COMPONENT, "data": {"component_type": 3, "custom_id": "pick"}})
    assert dev._describe_interaction(body) == "select pick"


def test_describe_interaction_modal_submit():
    body = json.dumps({"type": MODAL_SUBMIT, "data": {"custom_id": "feedback"}})
    assert dev._describe_interaction(body) == "modal feedback"


def test_describe_interaction_unknown_type_falls_back_to_number():
    body = json.dumps({"type": 99})
    assert dev._describe_interaction(body) == "type 99"


# --- status colour and body formatting ---


def test_status_color_success_is_green():
    assert dev._status_color(200) == dev.GREEN


def test_status_color_client_error_is_yellow():
    assert dev._status_color(404) == dev.YELLOW


def test_status_color_server_error_is_red():
    assert dev._status_color(500) == dev.RED


def test_pretty_body_empty_returns_empty_string():
    assert dev._pretty_body("") == ""


def test_pretty_body_formats_json():
    assert dev._pretty_body('{"a":1}') == json.dumps({"a": 1}, indent=2)


def test_pretty_body_passes_through_non_json():
    assert dev._pretty_body("not json") == "not json"


def test_pretty_body_truncates_long_output():
    body = json.dumps({"text": "x" * dev._MAX_LOGGED_BODY * 3})
    full_pretty = json.dumps(json.loads(body), indent=2)
    pretty = dev._pretty_body(body)
    assert pretty.endswith("more chars)")
    assert len(pretty) < len(full_pretty)


def test_log_request_verbose_prints_indented_body(capsys):
    dev._log_request("ping", 200, 12.3, json.dumps({"a": 1}), verbose=True)
    assert '"a": 1' in capsys.readouterr().out
