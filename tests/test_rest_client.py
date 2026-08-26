"""_rest/_client.py's _send(): the real (unmocked) persistent-connection
transport every other test in this suite bypasses by mocking _send itself."""

import urllib.error
import urllib.request

import pytest

import cordless._rest._client as _client


class _FakeResponse:
    """Real http.client.HTTPResponse objects support the context-manager
    protocol (via io.IOBase); _send()'s callers rely on that, so this fake
    needs to as well."""

    def __init__(self, status, body):
        self.status = status
        self.reason = ""
        self.headers = {}
        self._body = body

    def read(self):
        return self._body

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeHTTPSConnection:
    requests = []
    responses = []
    raise_once = None  # set to an exception instance to make the next request() raise
    close_calls = 0

    def __init__(self, host, timeout=None):
        self.host = host
        self.timeout = timeout

    def request(self, method, url, body, headers):
        cls = FakeHTTPSConnection
        if cls.raise_once is not None:
            exc = cls.raise_once
            cls.raise_once = None
            raise exc
        cls.requests.append({"method": method, "url": url, "body": body, "headers": headers, "timeout": self.timeout})

    def getresponse(self):
        status, body = FakeHTTPSConnection.responses.pop(0) if FakeHTTPSConnection.responses else (200, b"{}")
        return _FakeResponse(status, body)

    def close(self):
        FakeHTTPSConnection.close_calls += 1


@pytest.fixture
def fake_conn(monkeypatch):
    FakeHTTPSConnection.requests = []
    FakeHTTPSConnection.responses = []
    FakeHTTPSConnection.raise_once = None
    FakeHTTPSConnection.close_calls = 0
    monkeypatch.setattr(_client.http.client, "HTTPSConnection", FakeHTTPSConnection)
    monkeypatch.setattr(_client, "_conn", None)
    return FakeHTTPSConnection


def _request(method="GET", path="/api/v10/gateway", body=None, headers=None):
    return urllib.request.Request(f"https://discord.com{path}", data=body, headers=headers or {}, method=method)


def test_send_reuses_the_same_connection_across_calls(fake_conn):
    _client._send(_request())
    first_conn = _client._conn
    _client._send(_request())

    assert _client._conn is first_conn
    assert len(fake_conn.requests) == 2


def test_send_reconnects_when_kept_alive_connection_is_dropped(fake_conn, monkeypatch):
    """A warm connection reused across invocations can get closed by Discord's
    end between requests - _send must close it, open a fresh one, and retry
    the same request once rather than blowing up."""
    monkeypatch.setattr(_client, "_conn", fake_conn("discord.com"))
    fake_conn.raise_once = OSError("connection reset by peer")
    fake_conn.responses = [(200, b"{}")]

    with _client._send(_request()) as resp:
        assert resp.read() == b"{}"

    assert fake_conn.close_calls == 1
    assert len(fake_conn.requests) == 1  # only the retried request actually went through


def test_send_returns_readable_response_on_success(fake_conn):
    fake_conn.responses = [(200, b'{"id": "1"}')]

    with _client._send(_request()) as resp:
        assert resp.status == 200
        assert resp.read() == b'{"id": "1"}'


def test_send_raises_http_error_on_non_2xx(fake_conn):
    fake_conn.responses = [(404, b'{"message": "Not Found"}')]

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _client._send(_request())

    assert exc_info.value.code == 404
    assert exc_info.value.read() == b'{"message": "Not Found"}'


def test_send_forwards_method_path_body_and_headers(fake_conn):
    _client._send(_request(method="POST", path="/api/v10/channels/20/messages", body=b'{"content": "hi"}'))

    req = fake_conn.requests[0]
    assert req["method"] == "POST"
    assert req["url"] == "/api/v10/channels/20/messages"
    assert req["body"] == b'{"content": "hi"}'
