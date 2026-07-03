import json
import os
import sys
from unittest.mock import patch

import pytest

from cordless.cli import main

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


@pytest.fixture(autouse=True)
def _fixtures_on_path():
    sys.path.insert(0, FIXTURES_DIR)
    yield
    sys.path.remove(FIXTURES_DIR)
    sys.modules.pop("sample_app", None)


def test_register_resolves_bot_and_prints_summary(capsys):
    responses = [_FakeResponse({"id": "app-id"}), _FakeResponse([{"id": "1", "name": "ping"}])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses):
        main(["register", "sample_app:bot", "--token", "tok"])

    out = capsys.readouterr().out
    assert "Registered 1 command(s) globally: ping" in out


def test_register_scopes_to_guild(capsys):
    responses = [_FakeResponse({"id": "app-id"}), _FakeResponse([{"id": "1", "name": "ping"}])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses):
        main(["register", "sample_app:bot", "--token", "tok", "--guild-id", "guild-1"])

    out = capsys.readouterr().out
    assert "guild guild-1" in out


def test_register_uses_token_from_environment(monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "env-token")
    responses = [_FakeResponse({"id": "app-id"}), _FakeResponse([])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        main(["register", "sample_app:bot"])

    lookup_request = urlopen.call_args_list[0].args[0]
    assert lookup_request.get_header("Authorization") == "Bot env-token"
    assert "Registered 0 command(s) globally" in capsys.readouterr().out


def test_register_requires_a_token(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    with pytest.raises(SystemExit):
        main(["register", "sample_app:bot"])


def test_register_rejects_bad_target_syntax():
    with pytest.raises(SystemExit):
        main(["register", "sample_app", "--token", "tok"])


def test_register_rejects_missing_attribute():
    with pytest.raises(SystemExit):
        main(["register", "sample_app:missing", "--token", "tok"])
