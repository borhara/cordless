import os
import sys
from unittest.mock import patch

import pytest

from cordless.cli import main

from conftest import FakeDiscordResponse

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(autouse=True)
def _fixtures_on_path():
    sys.path.insert(0, FIXTURES_DIR)
    yield
    sys.path.remove(FIXTURES_DIR)
    sys.modules.pop("sample_app", None)


def test_register_resolves_bot_and_prints_summary(capsys):
    responses = [FakeDiscordResponse({"id": "app-id"}), FakeDiscordResponse([{"id": "1", "name": "ping"}])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses):
        main(["register", "sample_app:bot", "--token", "tok"])

    assert "Registered 1 command(s) globally: ping" in capsys.readouterr().out


def test_register_scopes_to_guild(capsys):
    responses = [FakeDiscordResponse({"id": "app-id"}), FakeDiscordResponse([{"id": "1", "name": "ping"}])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses):
        main(["register", "sample_app:bot", "--token", "tok", "--guild-id", "guild-1"])

    assert "guild guild-1" in capsys.readouterr().out


def test_register_uses_token_from_environment(monkeypatch, capsys):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "env-token")
    responses = [FakeDiscordResponse({"id": "app-id"}), FakeDiscordResponse([])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        main(["register", "sample_app:bot"])

    assert urlopen.call_args_list[0].args[0].get_header("Authorization") == "Bot env-token"
    assert "Registered 0 command(s) globally" in capsys.readouterr().out


def test_register_via_client_credentials(capsys):
    responses = [FakeDiscordResponse({"access_token": "bearer-tok"}),
                 FakeDiscordResponse([{"id": "1", "name": "ping"}])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        main(["register", "sample_app:bot", "--client-id", "cid", "--client-secret", "csecret"])

    assert urlopen.call_args_list[1].args[0].get_header("Authorization") == "Bearer bearer-tok"
    assert "Registered 1 command(s) globally: ping" in capsys.readouterr().out


def test_register_requires_credentials(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_CLIENT_ID", raising=False)
    monkeypatch.delenv("DISCORD_CLIENT_SECRET", raising=False)

    with pytest.raises(SystemExit):
        main(["register", "sample_app:bot"])


def test_register_rejects_bad_target_syntax():
    with pytest.raises(SystemExit):
        main(["register", "sample_app", "--token", "tok"])


def test_register_rejects_missing_attribute():
    with pytest.raises(SystemExit):
        main(["register", "sample_app:missing", "--token", "tok"])
