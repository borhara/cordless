from cordless._env import read_dotenv, resolve_environment


def test_resolve_environment_prefers_explicit(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    assert resolve_environment("staging") == "staging"


def test_resolve_environment_falls_back_to_env_var(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    assert resolve_environment(None) == "prod"


def test_resolve_environment_none_when_unset(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    assert resolve_environment(None) is None


def test_read_dotenv_without_environment_reads_base_only(tmp_path):
    (tmp_path / ".env").write_text("KEY=base\n")
    assert read_dotenv(str(tmp_path)) == {"KEY": "base"}


def test_read_dotenv_overlay_overrides_base(tmp_path):
    (tmp_path / ".env").write_text("KEY=base\nBASE_ONLY=x\n")
    (tmp_path / ".env.prod").write_text("KEY=prod\n")
    assert read_dotenv(str(tmp_path), "prod") == {"KEY": "prod", "BASE_ONLY": "x"}


def test_read_dotenv_missing_overlay_falls_back_to_base(tmp_path):
    (tmp_path / ".env").write_text("KEY=base\n")
    assert read_dotenv(str(tmp_path), "staging") == {"KEY": "base"}


def test_read_dotenv_missing_base_uses_overlay_only(tmp_path):
    (tmp_path / ".env.prod").write_text("KEY=prod\n")
    assert read_dotenv(str(tmp_path), "prod") == {"KEY": "prod"}
