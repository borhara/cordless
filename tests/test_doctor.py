import json
import os
from unittest.mock import patch

import boto3
import pytest
from conftest import FakeDiscordResponse, make_http_error
from moto import mock_aws

from cordless.doctor import (
    check_aws_credentials,
    check_discord_config,
    check_env_drift,
    check_iam_role,
    run,
)

REGION = "us-east-1"

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", REGION)

_TRUST_POLICY = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}
        ],
    }
)
_BASIC_POLICY_DOC = json.dumps(
    {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "logs:*", "Resource": "*"}]}
)


def _make_role(iam, name="test-role"):
    return iam.create_role(RoleName=name, AssumeRolePolicyDocument=_TRUST_POLICY)["Role"]["Arn"]


def _attach_basic_policy(iam, role_name):
    arn = iam.create_policy(PolicyName="AWSLambdaBasicExecutionRole", PolicyDocument=_BASIC_POLICY_DOC)["Policy"]["Arn"]
    iam.attach_role_policy(RoleName=role_name, PolicyArn=arn)


@pytest.fixture
def iam_client():
    with mock_aws():
        yield boto3.client("iam", region_name=REGION)


# --- check_aws_credentials ---


def test_check_aws_credentials_ok():
    with mock_aws():
        ok, session, detail = check_aws_credentials(REGION)

    assert ok is True
    assert session is not None
    assert "account" in detail


def test_check_aws_credentials_failure(monkeypatch):
    monkeypatch.setattr(
        "cordless._aws.get_session", lambda region, validate=True: (_ for _ in ()).throw(SystemExit("no creds found"))
    )

    ok, session, detail = check_aws_credentials(REGION)

    assert ok is False
    assert session is None
    assert "no creds found" in detail


# --- check_iam_role ---


def test_check_iam_role_not_found(iam_client):
    checks = check_iam_role(iam_client, "missing-role")
    assert checks == [("fail", "IAM role", "'missing-role' not found")]


def test_check_iam_role_exists_without_basic_policy(iam_client):
    _make_role(iam_client, "my-role")
    checks = check_iam_role(iam_client, "my-role")

    by_label = {label: (sev, detail) for sev, label, detail in checks}
    assert by_label["IAM role"][0] == "ok"
    assert by_label["Basic execution policy"] == ("fail", "not attached")


def test_check_iam_role_with_basic_policy(iam_client):
    _make_role(iam_client, "my-role")
    _attach_basic_policy(iam_client, "my-role")
    checks = check_iam_role(iam_client, "my-role")

    by_label = {label: (sev, detail) for sev, label, detail in checks}
    assert by_label["Basic execution policy"] == ("ok", "attached")


def test_check_iam_role_worker_invoke_policy_missing(iam_client):
    _make_role(iam_client, "my-role")
    _attach_basic_policy(iam_client, "my-role")
    checks = check_iam_role(iam_client, "my-role", defer_worker="my-worker")

    by_label = {label: sev for sev, label, _ in checks}
    assert by_label["Worker invoke policy"] == "fail"


def test_check_iam_role_worker_invoke_policy_present(iam_client):
    _make_role(iam_client, "my-role")
    _attach_basic_policy(iam_client, "my-role")
    iam_client.put_role_policy(
        RoleName="my-role", PolicyName="cordless-worker-invoke", PolicyDocument=_BASIC_POLICY_DOC
    )
    checks = check_iam_role(iam_client, "my-role", defer_worker="my-worker")

    by_label = {label: sev for sev, label, _ in checks}
    assert by_label["Worker invoke policy"] == "ok"


def test_check_iam_role_ratelimit_policy_missing(iam_client):
    _make_role(iam_client, "my-role")
    _attach_basic_policy(iam_client, "my-role")
    checks = check_iam_role(iam_client, "my-role", ratelimit=True)

    by_label = {label: sev for sev, label, _ in checks}
    assert by_label["Rate limit table policy"] == "fail"


# --- check_discord_config ---


def test_check_discord_config_missing_public_key():
    checks = check_discord_config({})
    by_label = {label: (sev, detail) for sev, label, detail in checks}
    assert by_label["DISCORD_PUBLIC_KEY"] == ("fail", "missing")


def test_check_discord_config_malformed_public_key():
    checks = check_discord_config({"DISCORD_PUBLIC_KEY": "not-hex"})
    by_label = {label: sev for sev, label, _ in checks}
    assert by_label["DISCORD_PUBLIC_KEY"] == "fail"


def test_check_discord_config_valid_public_key():
    checks = check_discord_config({"DISCORD_PUBLIC_KEY": "a" * 64})
    by_label = {label: sev for sev, label, _ in checks}
    assert by_label["DISCORD_PUBLIC_KEY"] == "ok"


def test_check_discord_config_valid_bot_token():
    env = {"DISCORD_PUBLIC_KEY": "a" * 64, "DISCORD_BOT_TOKEN": "tok"}
    with patch("cordless.register.urllib.request.urlopen", return_value=FakeDiscordResponse({"id": "app-1"})):
        checks = check_discord_config(env)

    by_label = {label: (sev, detail) for sev, label, detail in checks}
    assert by_label["Bot token"][0] == "ok"
    assert "app-1" in by_label["Bot token"][1]


def test_check_discord_config_invalid_bot_token():
    env = {"DISCORD_PUBLIC_KEY": "a" * 64, "DISCORD_BOT_TOKEN": "bad-tok"}
    err = make_http_error(401, body=b'{"message": "401: Unauthorized"}')
    with patch("cordless.register.urllib.request.urlopen", side_effect=err):
        checks = check_discord_config(env)

    by_label = {label: sev for sev, label, _ in checks}
    assert by_label["Bot token"] == "fail"


def test_check_discord_config_client_credentials():
    env = {"DISCORD_PUBLIC_KEY": "a" * 64, "DISCORD_CLIENT_ID": "cid", "DISCORD_CLIENT_SECRET": "csecret"}
    with patch(
        "cordless.register.urllib.request.urlopen", return_value=FakeDiscordResponse({"access_token": "bearer"})
    ):
        checks = check_discord_config(env)

    by_label = {label: sev for sev, label, _ in checks}
    assert by_label["Client credentials"] == "ok"


def test_check_discord_config_no_credentials_at_all():
    checks = check_discord_config({"DISCORD_PUBLIC_KEY": "a" * 64})
    by_label = {label: sev for sev, label, _ in checks}
    assert by_label["Discord credentials"] == "fail"


# --- check_env_drift ---


class _FakeLambdaClient:
    def __init__(self, env_vars):
        self._env_vars = env_vars

    def get_function_configuration(self, FunctionName):
        return {"Environment": {"Variables": self._env_vars}}


def test_check_env_drift_matching_secret_reports_no_value():
    lam = _FakeLambdaClient({"DISCORD_BOT_TOKEN": "same-token"})
    checks = check_env_drift(lam, "my-fn", {"DISCORD_BOT_TOKEN": "same-token"})

    assert checks == [("ok", "DISCORD_BOT_TOKEN (deployed)", "matches local")]


def test_check_env_drift_mismatched_secret_does_not_leak_value():
    lam = _FakeLambdaClient({"DISCORD_BOT_TOKEN": "deployed-secret-value"})
    checks = check_env_drift(lam, "my-fn", {"DISCORD_BOT_TOKEN": "local-secret-value"})

    assert checks == [("fail", "DISCORD_BOT_TOKEN (deployed)", "differs from local")]
    detail = checks[0][2]
    assert "deployed-secret-value" not in detail
    assert "local-secret-value" not in detail


def test_check_env_drift_mismatched_non_secret_shows_values():
    lam = _FakeLambdaClient({"DISCORD_GUILD_ID": "111"})
    checks = check_env_drift(lam, "my-fn", {"DISCORD_GUILD_ID": "222"})

    assert checks == [("fail", "DISCORD_GUILD_ID (deployed)", "deployed='111', local='222'")]


def test_check_env_drift_missing_on_deployed_function():
    lam = _FakeLambdaClient({})
    checks = check_env_drift(lam, "my-fn", {"DISCORD_PUBLIC_KEY": "a" * 64})

    assert checks == [("fail", "DISCORD_PUBLIC_KEY (deployed)", "set locally but missing on the deployed function")]


def test_check_env_drift_missing_locally():
    lam = _FakeLambdaClient({"DISCORD_PUBLIC_KEY": "a" * 64})
    checks = check_env_drift(lam, "my-fn", {})

    assert checks == [("fail", "DISCORD_PUBLIC_KEY (deployed)", "set on the deployed function but missing locally")]


def test_check_env_drift_skips_keys_absent_everywhere():
    lam = _FakeLambdaClient({})
    checks = check_env_drift(lam, "my-fn", {})
    assert checks == []


# --- run() ---


def test_run_reports_undeployed_function_as_warn_not_fail():
    with mock_aws():
        sections, ok = run(
            function_name="my-fn", role_name=None, region=REGION, local_env={"DISCORD_PUBLIC_KEY": "a" * 64}
        )

    lambda_section = next(checks for title, checks in sections if title == "Lambda")
    assert lambda_section[0][0] == "warn"
    assert "not deployed yet" in lambda_section[0][2]
    # Discord credentials are still missing, so overall ok is still False
    assert ok is False


def test_run_threads_routes_into_deployed_function_check():
    with mock_aws(), patch("cordless.doctor.check_deployed_function", return_value=[]) as cdf:
        run(
            function_name="my-fn",
            role_name=None,
            region=REGION,
            local_env={"DISCORD_PUBLIC_KEY": "a" * 64},
            routes=[("GET", "/healthz")],
        )

    assert cdf.call_args.args[-1] == [("GET", "/healthz")]


def test_run_ok_false_when_public_key_missing():
    with mock_aws():
        sections, ok = run(function_name=None, role_name=None, region=REGION, local_env={})

    assert ok is False


def test_run_skips_iam_and_lambda_when_nothing_configured():
    with mock_aws():
        sections, ok = run(
            function_name=None, role_name=None, region=REGION, local_env={"DISCORD_PUBLIC_KEY": "a" * 64}
        )

    iam_section = next(checks for title, checks in sections if title == "IAM")
    lambda_section = next(checks for title, checks in sections if title == "Lambda")
    assert iam_section[0][0] == "warn"
    assert lambda_section[0][0] == "warn"
