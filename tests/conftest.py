import io
import json
import urllib.error


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


def make_http_error(code, body=b"", headers=None):
    """A real urllib.error.HTTPError, for simulating a non-2xx urlopen() response."""
    return urllib.error.HTTPError(
        url="https://discord.com/api/v10", code=code, msg="", hdrs=headers, fp=io.BytesIO(body)
    )
