"""Deferred flow: router ACK + worker invoke, worker-mode dispatch, followup PATCH, crons."""
import json

import pytest

import cordless.defer
from cordless.app import Cordless
from cordless.worker import make_worker_handler


def _handle(bot, payload):
    return bot.handle({"body": json.dumps(payload)})


def _body(result):
    return json.loads(result["body"])


@pytest.fixture
def invoked(monkeypatch):
    calls = []
    monkeypatch.setattr(cordless.defer, "invoke_worker", lambda fn, interaction: calls.append((fn, interaction)))
    monkeypatch.setenv("CORDLESS_WORKER_FUNCTION", "my-worker")
    return calls


@pytest.fixture
def patched(monkeypatch):
    calls = []
    monkeypatch.setattr(cordless.defer, "patch_followup", lambda app_id, token, payload: calls.append(payload))
    return calls


# --- Router defer branch ---

def test_deferred_command_acks_type_5_and_invokes_worker(invoked):
    bot = Cordless()

    @bot.command("slow", defer=True)
    async def slow(ctx):
        await ctx.send("done")

    result = _handle(bot, {"type": 2, "data": {"name": "slow"}, "id": "1", "token": "tok"})
    assert _body(result)["type"] == 5
    assert invoked[0][0] == "my-worker"
    assert invoked[0][1]["data"]["name"] == "slow"


def test_deferred_button_acks_type_6_and_invokes_worker(invoked):
    bot = Cordless()

    @bot.button("slow_btn", defer=True)
    async def slow_btn(ctx):
        await ctx.send("done")

    result = _handle(bot, {"type": 3, "data": {"custom_id": "slow_btn"}, "id": "1", "token": "tok"})
    assert _body(result)["type"] == 6
    assert invoked[0][0] == "my-worker"


def test_deferred_command_without_worker_env_returns_400(monkeypatch):
    monkeypatch.delenv("CORDLESS_WORKER_FUNCTION", raising=False)
    bot = Cordless()

    @bot.command("slow", defer=True)
    async def slow(ctx):
        await ctx.send("done")

    result = _handle(bot, {"type": 2, "data": {"name": "slow"}, "id": "1", "token": "tok"})
    assert result["statusCode"] == 400
    assert "CORDLESS_WORKER_FUNCTION" in _body(result)["error"]


# --- Worker-mode dispatch ---

def test_worker_dispatch_sends_via_followup(patched):
    bot = Cordless()

    @bot.command("slow", defer=True)
    async def slow(ctx):
        await ctx.send("finally done")

    handler = make_worker_handler(bot)
    handler({"type": 2, "data": {"name": "slow"}, "id": "1", "token": "tok", "application_id": "app"})

    assert patched[0]["content"] == "finally done"


def test_worker_dispatch_reraises_handler_errors(patched):
    bot = Cordless()

    @bot.command("boom", defer=True)
    async def boom(ctx):
        raise ValueError("nope")

    handler = make_worker_handler(bot)
    with pytest.raises(ValueError):
        handler({"type": 2, "data": {"name": "boom"}, "id": "1", "token": "tok", "application_id": "app"})


# --- Followup PATCH (mocked HTTPSConnection) ---

class FakeHTTPSConnection:
    requests = []
    responses = []  # list of (status, body) consumed per request

    def __init__(self, host, timeout=None):
        self.host = host
        self.timeout = timeout

    def request(self, method, url, body, headers):
        FakeHTTPSConnection.requests.append({"method": method, "url": url, "body": body, "headers": headers, "timeout": self.timeout})

    def getresponse(self):
        status, body = FakeHTTPSConnection.responses.pop(0) if FakeHTTPSConnection.responses else (200, b"{}")
        return type("R", (), {"status": status, "read": lambda self: body})()

    def close(self):
        pass


@pytest.fixture
def fake_conn(monkeypatch):
    FakeHTTPSConnection.requests = []
    FakeHTTPSConnection.responses = []
    monkeypatch.setattr(cordless.defer, "HTTPSConnection", FakeHTTPSConnection)
    return FakeHTTPSConnection


def test_followup_with_multiple_files_uploads_all(fake_conn):
    cordless.defer.patch_followup_with_files(
        "app", "tok", {"content": "hi"},
        [("card.png", b"png-bytes"), ("log.txt", b"text-bytes")],
    )

    body = fake_conn.requests[0]["body"]
    assert b'filename="card.png"' in body
    assert b'Content-Type: image/png' in body
    assert b'filename="log.txt"' in body
    assert b'Content-Type: text/plain' in body
    assert b"png-bytes" in body and b"text-bytes" in body


def test_followup_content_type_falls_back_to_octet_stream(fake_conn):
    cordless.defer.patch_followup_with_files("app", "tok", {}, [("blob.xyz123", b"x")])
    assert b"Content-Type: application/octet-stream" in fake_conn.requests[0]["body"]


def test_patch_retries_on_404(fake_conn, monkeypatch):
    monkeypatch.setattr(cordless.defer.time, "sleep", lambda s: None)
    fake_conn.responses = [(404, b"{}"), (200, b"{}")]

    status, _ = cordless.defer.patch_followup("app", "tok", {"content": "hi"})

    assert status == 200
    assert len(fake_conn.requests) == 2


def test_patch_retries_on_429_with_retry_after(fake_conn, monkeypatch):
    sleeps = []
    monkeypatch.setattr(cordless.defer.time, "sleep", lambda s: sleeps.append(s))
    fake_conn.responses = [(429, json.dumps({"retry_after": 0.25}).encode()), (200, b"{}")]

    status, _ = cordless.defer.patch_followup("app", "tok", {"content": "hi"})

    assert status == 200
    assert sleeps == [0.25]


def test_patch_gives_up_after_retries(fake_conn, monkeypatch):
    monkeypatch.setattr(cordless.defer.time, "sleep", lambda s: None)
    fake_conn.responses = [(404, b"{}"), (404, b"{}"), (404, b"{}")]

    status, _ = cordless.defer.patch_followup("app", "tok", {})

    assert status == 404
    assert len(fake_conn.requests) == 3


def test_connection_has_timeout(fake_conn):
    cordless.defer.patch_followup("app", "tok", {})
    assert fake_conn.requests[0]["timeout"] == cordless.defer._TIMEOUT


# --- Crons ---

def test_cron_runs_via_bot_handler():
    bot = Cordless()
    ran = []

    @bot.cron("rate(1 day)")
    async def daily():
        ran.append("daily")

    handler = bot.handler()
    handler({"_cordless_cron": "daily"})
    assert ran == ["daily"]


def test_cron_runs_via_worker_handler():
    bot = Cordless()
    ran = []

    @bot.cron("rate(1 hour)", name="tick")
    async def whatever():
        ran.append("tick")

    handler = make_worker_handler(bot)
    handler({"_cordless_cron": "tick"})
    assert ran == ["tick"]


def test_unknown_cron_raises():
    from cordless.errors import CordlessError
    bot = Cordless()
    with pytest.raises(CordlessError):
        bot.run_cron("ghost")


def test_cron_schedules_exposed_for_deploy():
    bot = Cordless()

    @bot.cron("rate(1 day)")
    async def daily(): pass

    @bot.cron("cron(0 12 * * ? *)", name="noon")
    async def noon_handler(): pass

    assert bot.crons["daily"]["schedule"] == "rate(1 day)"
    assert bot.crons["noon"]["schedule"] == "cron(0 12 * * ? *)"
