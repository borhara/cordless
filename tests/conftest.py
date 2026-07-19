import json

import pytest


class FakeDiscordResponse:
    """Minimal stub for urllib.request.urlopen responses."""

    def __init__(self, payload):
        self._payload = payload
        self.headers = {}

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeAppHTTPSConnection:
    """Stub for cordless.app.HTTPSConnection. One instance per fresh connection,
    but requests/responses are tracked on the class so tests can see every
    call even across a reconnect."""

    requests = []
    responses = []  # list of (status, headers, body) consumed per request
    raise_once = None  # set to an exception instance to make the next request() raise
    close_calls = 0

    def __init__(self, host):
        self.host = host

    def request(self, method, path, body, headers):
        cls = FakeAppHTTPSConnection
        if cls.raise_once is not None:
            exc = cls.raise_once
            cls.raise_once = None
            raise exc
        cls.requests.append({"method": method, "path": path, "body": body, "headers": headers})

    def getresponse(self):
        status, headers, body = FakeAppHTTPSConnection.responses.pop(0)
        return type("R", (), {"status": status, "headers": headers, "read": lambda self: body})()

    def close(self):
        FakeAppHTTPSConnection.close_calls += 1


@pytest.fixture
def fake_app_conn(monkeypatch):
    import cordless.app

    FakeAppHTTPSConnection.requests = []
    FakeAppHTTPSConnection.responses = []
    FakeAppHTTPSConnection.raise_once = None
    FakeAppHTTPSConnection.close_calls = 0
    monkeypatch.setattr(cordless.app, "HTTPSConnection", FakeAppHTTPSConnection)
    monkeypatch.setattr(cordless.app, "_conn", None)
    return FakeAppHTTPSConnection
