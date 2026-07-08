import os
import sys
from unittest.mock import patch

import pytest
from conftest import FakeDiscordResponse

from cordless.cli import _pick, main

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
    responses = [
        FakeDiscordResponse({"access_token": "bearer-tok"}),
        FakeDiscordResponse([{"id": "1", "name": "ping"}]),
    ]

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


def test_register_prefers_client_credentials_over_token(capsys, monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "should-not-be-used")
    responses = [
        FakeDiscordResponse({"access_token": "bearer-tok"}),
        FakeDiscordResponse([{"id": "1", "name": "ping"}]),
    ]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        main(["register", "sample_app:bot", "--client-id", "cid", "--client-secret", "csecret"])

    assert urlopen.call_args_list[1].args[0].get_header("Authorization") == "Bearer bearer-tok"


# ---------------------------------------------------------------------------
# cron
# ---------------------------------------------------------------------------


def test_cron_runs_handler(monkeypatch):
    import sample_app

    sample_app.cron_calls.clear()
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "tok")

    main(["cron", "hourly", "sample_app:bot", "--source", FIXTURES_DIR])

    assert sample_app.cron_calls == ["hourly"]


def test_cron_rejects_unknown_name():
    with pytest.raises(SystemExit, match="unknown_cron"):
        main(["cron", "unknown_cron", "sample_app:bot", "--source", FIXTURES_DIR])


# ---------------------------------------------------------------------------
# _pick
# ---------------------------------------------------------------------------


def test_pick_returns_first_non_none():
    assert _pick(None, 0, "x") == 0
    assert _pick(None, None, "x") == "x"
    assert _pick("a", "b") == "a"


def test_pick_returns_none_when_all_none():
    assert _pick(None, None, None) is None


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def test_init_creates_scaffold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["init", "mybot"])
    assert (tmp_path / "lambda_function.py").exists()
    assert (tmp_path / "cordless.toml").exists()
    assert (tmp_path / ".env.example").exists()
    assert "mybot" in (tmp_path / "cordless.toml").read_text()
    # the defer wiring line ships commented out so it's discoverable
    assert "# worker_handler = bot.worker_handler" in (tmp_path / "lambda_function.py").read_text()


def test_init_skips_existing_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "lambda_function.py").write_text("existing")
    main(["init"])
    assert (tmp_path / "lambda_function.py").read_text() == "existing"
    assert "already exists" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# destroy
# ---------------------------------------------------------------------------


def test_destroy_yes_skips_prompt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cordless.toml").write_text('[deploy]\nfunction = "mybot"\nregion = "us-east-1"\n')
    with patch("cordless.deploy.destroy") as mock_destroy:
        main(["destroy", "--yes"])
    mock_destroy.assert_called_once()
    assert mock_destroy.call_args.kwargs["function_name"] == "mybot"


def test_destroy_prompt_aborts_on_no(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cordless.toml").write_text('[deploy]\nfunction = "mybot"\nregion = "us-east-1"\n')
    monkeypatch.setattr("builtins.input", lambda _: "n")
    with patch("cordless.deploy.destroy") as mock_destroy:
        with pytest.raises(SystemExit):
            main(["destroy"])
    mock_destroy.assert_not_called()


# ---------------------------------------------------------------------------
# deploy arg->config precedence
# ---------------------------------------------------------------------------


def test_deploy_args_take_precedence_over_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cordless.toml").write_text(
        '[deploy]\nfunction = "from-toml"\nregion = "eu-west-1"\n[deploy.env]\nDISCORD_PUBLIC_KEY = "key"\n'
    )
    with patch("cordless.deploy.deploy") as mock_deploy:
        main(["deploy", "--function", "from-arg", "--region", "us-east-1"])
    kwargs = mock_deploy.call_args.kwargs
    assert kwargs["function_name"] == "from-arg"
    assert kwargs["region"] == "us-east-1"


def test_deploy_falls_back_to_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cordless.toml").write_text(
        '[deploy]\nfunction = "from-toml"\nregion = "eu-west-1"\n[deploy.env]\nDISCORD_PUBLIC_KEY = "key"\n'
    )
    with patch("cordless.deploy.deploy") as mock_deploy:
        main(["deploy"])
    kwargs = mock_deploy.call_args.kwargs
    assert kwargs["function_name"] == "from-toml"
    assert kwargs["region"] == "eu-west-1"


def test_deploy_setup_resolves_against_source_not_cwd(tmp_path, monkeypatch):
    """A same-named module shadowing in cwd must not win over --source's copy."""
    cwd_dir = tmp_path / "cwd"
    project_dir = tmp_path / "project"
    cwd_dir.mkdir()
    project_dir.mkdir()

    (cwd_dir / "db.py").write_text("def create_tables():\n    raise AssertionError('wrong db.py loaded from cwd')\n")
    (project_dir / "db.py").write_text("calls = []\n\n\ndef create_tables():\n    calls.append(True)\n")

    monkeypatch.chdir(cwd_dir)
    monkeypatch.setattr(sys, "modules", dict(sys.modules))
    sys.modules.pop("db", None)
    try:
        with patch("cordless.deploy.deploy"):
            main(["deploy", "--source", str(project_dir), "--setup", "db:create_tables", "--function", "fn"])
        assert sys.modules["db"].calls == [True]
    finally:
        sys.modules.pop("db", None)
