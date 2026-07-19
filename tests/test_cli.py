import os
import sys
import time
from unittest.mock import patch

import boto3
import pytest
from conftest import FakeDiscordResponse
from moto import mock_aws

from cordless.cli import _environment_from_argv, _pick, main

_LOGS_REGION = "us-east-1"
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")

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


def test_register_env_alias_loads_dot_env_overlay(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    (tmp_path / ".env").write_text("DISCORD_BOT_TOKEN=dev-token\n")
    (tmp_path / ".env.prod").write_text("DISCORD_BOT_TOKEN=prod-token\n")
    responses = [FakeDiscordResponse({"id": "app-id"}), FakeDiscordResponse([])]

    with patch("cordless.register.urllib.request.urlopen", side_effect=responses) as urlopen:
        main(["register", "sample_app:bot", "--env", "prod"])

    assert urlopen.call_args_list[0].args[0].get_header("Authorization") == "Bot prod-token"


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


def test_cron_env_alias_loads_environment_overlay(tmp_path, monkeypatch):
    import sample_app

    sample_app.cron_calls.clear()
    monkeypatch.delenv("MARKER", raising=False)
    (tmp_path / ".env").write_text("MARKER=dev\n")
    (tmp_path / ".env.staging").write_text("MARKER=staging\n")

    main(["cron", "hourly", "sample_app:bot", "--source", str(tmp_path), "--env", "staging"])

    assert sample_app.cron_calls == ["hourly"]
    assert os.environ.pop("MARKER") == "staging"


# ---------------------------------------------------------------------------
# flag abbreviation
# ---------------------------------------------------------------------------


def test_abbreviated_flag_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        main(["deploy", "--function", "x", "--bundle"])


def test_full_flag_name_still_works(tmp_path, monkeypatch):
    import cordless.cli

    captured = {}
    monkeypatch.setattr(cordless.cli, "_deploy", lambda args: captured.setdefault("args", args))
    monkeypatch.chdir(tmp_path)

    main(["deploy", "--function", "x", "--bundle-cordless"])

    assert captured["args"].bundle_cordless is True


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
    main(["init", "mybot", "--endpoint", "function_url"])
    assert (tmp_path / "lambda_function.py").exists()
    assert (tmp_path / "cordless.toml").exists()
    assert (tmp_path / ".env.example").exists()
    assert "mybot" in (tmp_path / "cordless.toml").read_text()
    # the defer wiring line ships commented out so it's discoverable
    assert "# worker_handler = bot.worker_handler" in (tmp_path / "lambda_function.py").read_text()


def test_init_skips_existing_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "lambda_function.py").write_text("existing")
    main(["init", "--endpoint", "function_url"])
    assert (tmp_path / "lambda_function.py").read_text() == "existing"
    assert "already exists" in capsys.readouterr().out


def test_init_endpoint_flag_writes_toml_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["init", "--endpoint", "api_gateway"])
    assert 'endpoint = "api_gateway"' in (tmp_path / "cordless.toml").read_text()


def test_init_without_endpoint_flag_prompts_when_interactive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    with patch("builtins.input", return_value="2"):
        main(["init"])
    assert 'endpoint = "api_gateway"' in (tmp_path / "cordless.toml").read_text()


def test_init_prompt_accepts_endpoint_name_not_just_number(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    with patch("builtins.input", return_value="function_url"):
        main(["init"])
    assert 'endpoint = "function_url"' in (tmp_path / "cordless.toml").read_text()


def test_init_prompt_rejects_invalid_input_and_asks_again(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    with patch("builtins.input", side_effect=["banana", "1"]):
        main(["init"])
    assert 'endpoint = "function_url"' in (tmp_path / "cordless.toml").read_text()


def test_init_without_endpoint_flag_fails_fast_when_not_interactive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit, match="--endpoint"):
        main(["init"])
    assert not (tmp_path / "cordless.toml").exists()


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


def test_destroy_passes_ratelimit_flag_from_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cordless.toml").write_text('[deploy]\nfunction = "mybot"\nregion = "us-east-1"\nratelimit = true\n')
    with patch("cordless.deploy.destroy") as mock_destroy:
        main(["destroy", "--yes"])
    assert mock_destroy.call_args.kwargs["ratelimit"] is True


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


def test_deploy_passes_ratelimit_flag_from_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cordless.toml").write_text('[deploy]\nfunction = "mybot"\nregion = "us-east-1"\nratelimit = true\n')
    with patch("cordless.deploy.deploy") as mock_deploy:
        main(["deploy"])
    assert mock_deploy.call_args.kwargs["ratelimit"] is True


def test_deploy_ratelimit_defaults_to_false(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cordless.toml").write_text('[deploy]\nfunction = "mybot"\nregion = "us-east-1"\n')
    with patch("cordless.deploy.deploy") as mock_deploy:
        main(["deploy"])
    assert mock_deploy.call_args.kwargs["ratelimit"] is False


def test_deploy_env_flag_overlays_dot_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("DISCORD_PUBLIC_KEY=dev-key\nDISCORD_BOT_TOKEN=dev\n")
    (tmp_path / ".env.prod").write_text("DISCORD_PUBLIC_KEY=prod-key\n")
    with patch("cordless.deploy.deploy") as mock_deploy:
        main(["deploy", "--function", "fn", "--environment", "prod"])
    env = mock_deploy.call_args.kwargs["env"]
    assert env["DISCORD_PUBLIC_KEY"] == "prod-key"
    assert env["DISCORD_BOT_TOKEN"] == "dev"


def test_deploy_env_var_overlays_dot_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENV", "prod")
    (tmp_path / ".env").write_text("DISCORD_PUBLIC_KEY=dev-key\n")
    (tmp_path / ".env.prod").write_text("DISCORD_PUBLIC_KEY=prod-key\n")
    with patch("cordless.deploy.deploy") as mock_deploy:
        main(["deploy", "--function", "fn"])
    assert mock_deploy.call_args.kwargs["env"]["DISCORD_PUBLIC_KEY"] == "prod-key"


def test_deploy_missing_env_file_falls_back_to_dot_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("DISCORD_PUBLIC_KEY=dev-key\n")
    with patch("cordless.deploy.deploy") as mock_deploy:
        main(["deploy", "--function", "fn", "--environment", "staging"])
    assert mock_deploy.call_args.kwargs["env"]["DISCORD_PUBLIC_KEY"] == "dev-key"


def test_deploy_env_flag_key_value_still_works(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("DISCORD_PUBLIC_KEY=dev-key\n")
    with patch("cordless.deploy.deploy") as mock_deploy:
        main(["deploy", "--function", "fn", "--env", "DISCORD_PUBLIC_KEY=cli-key"])
    assert mock_deploy.call_args.kwargs["env"]["DISCORD_PUBLIC_KEY"] == "cli-key"


def test_deploy_env_flag_bare_value_selects_environment(tmp_path, monkeypatch):
    """A bare --env value (no "=") picks the .env.<name> overlay, like --environment."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("DISCORD_PUBLIC_KEY=dev-key\n")
    (tmp_path / ".env.dev").write_text("DISCORD_PUBLIC_KEY=dev-overlay-key\n")
    with patch("cordless.deploy.deploy") as mock_deploy:
        main(["deploy", "--function", "fn", "--env", "dev"])
    assert mock_deploy.call_args.kwargs["env"]["DISCORD_PUBLIC_KEY"] == "dev-overlay-key"


def test_deploy_env_flag_mixes_bare_name_and_key_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("DISCORD_PUBLIC_KEY=dev-key\n")
    (tmp_path / ".env.prod").write_text("DISCORD_PUBLIC_KEY=prod-key\n")
    with patch("cordless.deploy.deploy") as mock_deploy:
        main(["deploy", "--function", "fn", "--env", "prod", "--env", "EXTRA=1"])
    env = mock_deploy.call_args.kwargs["env"]
    assert env["DISCORD_PUBLIC_KEY"] == "prod-key"
    assert env["EXTRA"] == "1"


def test_environment_from_argv_env_flag_bare_value_is_a_name():
    assert _environment_from_argv(["deploy", "--env", "FOO=bar", "--function", "x"]) is None
    assert _environment_from_argv(["deploy", "--env", "dev"]) == "dev"
    assert _environment_from_argv(["deploy", "--environment", "prod"]) == "prod"
    assert _environment_from_argv(["register", "--env", "prod"]) == "prod"
    assert _environment_from_argv(["dev", "--env", "prod"]) == "prod"
    assert _environment_from_argv(["cron", "name", "--env", "staging"]) == "staging"


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


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------


def _seed_log_group(function_name, messages, region=_LOGS_REGION):
    cw = boto3.client("logs", region_name=region)
    log_group = f"/aws/lambda/{function_name}"
    cw.create_log_group(logGroupName=log_group)
    cw.create_log_stream(logGroupName=log_group, logStreamName="stream-1")
    now_ms = int(time.time() * 1000)
    cw.put_log_events(
        logGroupName=log_group,
        logStreamName="stream-1",
        logEvents=[{"timestamp": now_ms, "message": m} for m in messages],
    )
    return cw


def test_logs_requires_function_name_when_none_configured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="Function name required"):
        main(["logs", "--region", _LOGS_REGION])


def test_logs_worker_requires_defer_worker_in_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="no defer_worker configured"):
        main(["logs", "--worker", "--region", _LOGS_REGION])


def test_logs_requires_region(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    with pytest.raises(SystemExit, match="Region is required"):
        main(["logs", "--function", "my-fn"])


def test_logs_prints_matching_events(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        _seed_log_group("my-fn", ["hello from lambda"])
        main(["logs", "--function", "my-fn", "--region", _LOGS_REGION])

    assert "hello from lambda" in capsys.readouterr().out


class _FakeLogsClient:
    class exceptions:
        class ResourceNotFoundException(Exception):
            pass

    def __init__(self, pages):
        self._pages = list(pages)
        self.calls = 0

    def filter_log_events(self, **kwargs):
        self.calls += 1
        return self._pages.pop(0)


def test_logs_dedupes_events_seen_across_pagination(tmp_path, monkeypatch, capsys):
    """The same event id can show up in more than one filter_log_events page
    (a real risk when new events land mid-pagination) - it must only print
    once. moto always returns everything in a single page, so this drives a
    fake client directly to actually force the duplicate across two pages."""
    monkeypatch.chdir(tmp_path)

    event = {"eventId": "e1", "timestamp": int(time.time() * 1000), "message": "dup line"}
    fake_client = _FakeLogsClient([{"events": [event], "nextToken": "next"}, {"events": [event]}])

    class _FakeSession:
        def client(self, name):
            assert name == "logs"
            return fake_client

    monkeypatch.setattr("cordless._aws.get_session", lambda region, validate=False: _FakeSession())
    main(["logs", "--function", "my-fn", "--region", _LOGS_REGION])

    out = capsys.readouterr().out
    assert out.count("dup line") == 1
    assert fake_client.calls == 2  # both pages were actually fetched


def test_logs_missing_log_group_raises_helpful_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        with pytest.raises(SystemExit, match="Log group not found"):
            main(["logs", "--function", "does-not-exist", "--region", _LOGS_REGION])


def test_logs_worker_reads_defer_worker_from_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "cordless.toml").write_text('[deploy]\ndefer_worker = "my-fn-worker"\n')
    with mock_aws():
        _seed_log_group("my-fn-worker", ["worker log line"])
        main(["logs", "--worker", "--region", _LOGS_REGION])

    assert "worker log line" in capsys.readouterr().out


def test_logs_follow_polls_again_until_interrupted(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        _seed_log_group("my-fn", ["first line"])

        calls = []

        def fake_sleep(seconds):
            calls.append(seconds)
            raise KeyboardInterrupt

        monkeypatch.setattr(time, "sleep", fake_sleep)
        main(["logs", "--function", "my-fn", "--region", _LOGS_REGION, "--follow"])

    assert calls == [2]
    out = capsys.readouterr().out
    assert "first line" in out
    assert "following" in out
