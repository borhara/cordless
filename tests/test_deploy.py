import json
import os
import zipfile

import boto3
import pytest
from moto import mock_aws

import cordless.deploy
from cordless.deploy import (
    _allow_worker_invoke,
    _ensure_api_gateway,
    _function_exists,
    _wire_crons,
    deploy,
    destroy,
    ensure_iam_role,
    _publish_cordless_layer,
)

REGION = "us-east-1"
ACCOUNT_ID = "123456789012"

# moto needs fake credentials
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", REGION)

_BASIC_POLICY_DOC = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": "logs:*", "Resource": "*"}],
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_zip(tmp_path):
    p = tmp_path / "fn.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("lambda_function.py", "def handler(event, context): pass\n")
    return str(p)


def _make_role(iam, name="test-role"):
    trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}
            ],
        }
    )
    return iam.create_role(RoleName=name, AssumeRolePolicyDocument=trust)["Role"]["Arn"]


def _make_function(lam, name, role_arn, zip_path, runtime="python3.12"):
    with open(zip_path, "rb") as f:
        return lam.create_function(
            FunctionName=name,
            Runtime=runtime,
            Role=role_arn,
            Handler="lambda_function.handler",
            Code={"ZipFile": f.read()},
        )["FunctionArn"]


def _seed_lambda_execution_policy(iam):
    """Create a substitute for AWSLambdaBasicExecutionRole in the moto account and return its ARN."""
    arn = iam.create_policy(
        PolicyName="AWSLambdaBasicExecutionRole",
        PolicyDocument=_BASIC_POLICY_DOC,
    )["Policy"]["Arn"]
    return arn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def aws_clients():
    with mock_aws():
        yield {
            "iam": boto3.client("iam", region_name=REGION),
            "lam": boto3.client("lambda", region_name=REGION),
            "apigw": boto3.client("apigatewayv2", region_name=REGION),
            "events": boto3.client("events", region_name=REGION),
        }


@pytest.fixture
def aws_clients_with_policy(aws_clients, monkeypatch):
    """aws_clients + the basic execution policy seeded and constant patched."""
    policy_arn = _seed_lambda_execution_policy(aws_clients["iam"])
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", policy_arn)
    yield aws_clients


@pytest.fixture
def deploy_patches(monkeypatch, tmp_path):
    """Patch out filesystem/pip/upload; AWS calls go through moto."""

    def _fresh_zip(*a, **kw):
        # deploy() deletes the zip after use, so recreate it on each call
        return _minimal_zip(tmp_path)

    monkeypatch.setattr(cordless.deploy, "build_function_zip", _fresh_zip)
    monkeypatch.setattr(cordless.deploy, "_publish_cordless_layer", lambda *a, **kw: None)
    monkeypatch.setattr(cordless.deploy, "_cordless_version", lambda: "0.13.1")
    return tmp_path


def _base_deploy_kwargs(tmp_path, **overrides):
    kwargs = dict(
        function_name="my-bot",
        role_name="my-bot-role",
        handler="lambda_function.handler",
        source_dir=str(tmp_path),
        runtime="python3.12",
        layer_name="cordless",
        env={},
        region=REGION,
    )
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# ensure_iam_role
# ---------------------------------------------------------------------------


def test_ensure_iam_role_creates_role(aws_clients_with_policy):
    iam = aws_clients_with_policy["iam"]
    arn = ensure_iam_role(iam, "my-role")
    assert "my-role" in arn
    assert iam.get_role(RoleName="my-role")["Role"]["RoleName"] == "my-role"


def test_ensure_iam_role_is_idempotent(aws_clients_with_policy):
    iam = aws_clients_with_policy["iam"]
    arn1 = ensure_iam_role(iam, "my-role")
    arn2 = ensure_iam_role(iam, "my-role")
    assert arn1 == arn2


def test_ensure_iam_role_attaches_extra_policies(aws_clients_with_policy):
    iam = aws_clients_with_policy["iam"]
    extra_arn = iam.create_policy(PolicyName="ExtraPolicy", PolicyDocument=_BASIC_POLICY_DOC)["Policy"]["Arn"]
    ensure_iam_role(iam, "my-role", extra_policies=[extra_arn])
    arns = {p["PolicyArn"] for p in iam.list_attached_role_policies(RoleName="my-role")["AttachedPolicies"]}
    assert extra_arn in arns


# ---------------------------------------------------------------------------
# _function_exists
# ---------------------------------------------------------------------------


def test_function_exists_returns_false_for_missing(aws_clients):
    exists, arn = _function_exists(aws_clients["lam"], "nonexistent")
    assert exists is False
    assert arn is None


def test_function_exists_returns_true_when_present(aws_clients, tmp_path):
    iam, lam = aws_clients["iam"], aws_clients["lam"]
    role_arn = _make_role(iam)
    _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    exists, arn = _function_exists(lam, "my-fn")
    assert exists is True
    assert "my-fn" in arn


# ---------------------------------------------------------------------------
# _ensure_api_gateway
# ---------------------------------------------------------------------------


def test_ensure_api_gateway_creates_api(aws_clients, tmp_path):
    iam, lam, apigw = aws_clients["iam"], aws_clients["lam"], aws_clients["apigw"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    endpoint = _ensure_api_gateway(apigw, lam, "my-fn", fn_arn, REGION, ACCOUNT_ID)
    assert endpoint
    assert any(a["Name"] == "my-fn-api" for a in apigw.get_apis()["Items"])


def test_ensure_api_gateway_is_idempotent(aws_clients, tmp_path):
    iam, lam, apigw = aws_clients["iam"], aws_clients["lam"], aws_clients["apigw"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    url1 = _ensure_api_gateway(apigw, lam, "my-fn", fn_arn, REGION, ACCOUNT_ID)
    url2 = _ensure_api_gateway(apigw, lam, "my-fn", fn_arn, REGION, ACCOUNT_ID)
    assert url1 == url2
    assert len(apigw.get_apis()["Items"]) == 1


# ---------------------------------------------------------------------------
# _list_all_apis / _list_all_layer_versions (pagination)
# ---------------------------------------------------------------------------


class _FakePaginator:
    def __init__(self, pages, result_key):
        self._pages = pages
        self._result_key = result_key

    def paginate(self, **kwargs):
        return self

    def build_full_result(self):
        merged = [item for page in self._pages for item in page]
        return {self._result_key: merged}


class _FakeClient:
    def __init__(self, pages, result_key):
        self._paginator = _FakePaginator(pages, result_key)

    def get_paginator(self, name):
        return self._paginator


def test_list_all_apis_aggregates_every_page():
    client = _FakeClient([[{"Name": "a"}], [{"Name": "b"}]], "Items")
    assert cordless.deploy._list_all_apis(client) == [{"Name": "a"}, {"Name": "b"}]


def test_list_all_layer_versions_aggregates_every_page():
    client = _FakeClient([[{"Version": 1}], [{"Version": 2}]], "LayerVersions")
    assert cordless.deploy._list_all_layer_versions(client, "cordless") == [{"Version": 1}, {"Version": 2}]


def test_list_all_rules_aggregates_every_page():
    client = _FakeClient([[{"Name": "fn-cron-a"}], [{"Name": "fn-cron-b"}]], "Rules")
    assert cordless.deploy._list_all_rules(client, "fn-cron-") == [{"Name": "fn-cron-a"}, {"Name": "fn-cron-b"}]


# ---------------------------------------------------------------------------
# _allow_worker_invoke
# ---------------------------------------------------------------------------


def test_allow_worker_invoke_puts_inline_policy(aws_clients):
    iam = aws_clients["iam"]
    _make_role(iam, "my-role")
    worker_arn = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:my-worker"
    _allow_worker_invoke(iam, "my-role", worker_arn)
    raw = iam.get_role_policy(RoleName="my-role", PolicyName="cordless-worker-invoke")["PolicyDocument"]
    doc = raw if isinstance(raw, dict) else json.loads(raw)
    assert doc["Statement"][0]["Resource"] == worker_arn


# ---------------------------------------------------------------------------
# _wire_crons
# ---------------------------------------------------------------------------


def test_wire_crons_creates_rules(aws_clients, tmp_path):
    iam, lam, events = aws_clients["iam"], aws_clients["lam"], aws_clients["events"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _wire_crons(events, lam, "my-fn", "my-fn", fn_arn, {"daily": "rate(1 day)"})
    rules = events.list_rules(NamePrefix="my-fn-cron-")["Rules"]
    assert len(rules) == 1
    assert rules[0]["ScheduleExpression"] == "rate(1 day)"


def test_wire_crons_disables_retries(aws_clients, tmp_path):
    iam, lam, events = aws_clients["iam"], aws_clients["lam"], aws_clients["events"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _wire_crons(events, lam, "my-fn", "my-fn", fn_arn, {"tick": "rate(1 minute)"})
    cfg = lam.get_function_event_invoke_config(FunctionName="my-fn")
    assert cfg["MaximumRetryAttempts"] == 0


def test_wire_crons_sets_input_payload(aws_clients, tmp_path):
    iam, lam, events = aws_clients["iam"], aws_clients["lam"], aws_clients["events"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _wire_crons(events, lam, "my-fn", "my-fn", fn_arn, {"tick": "rate(5 minutes)"})
    targets = events.list_targets_by_rule(Rule="my-fn-cron-tick")["Targets"]
    assert json.loads(targets[0]["Input"]) == {"_cordless_cron": "tick"}


def test_wire_crons_removes_stale_rules(aws_clients, tmp_path):
    iam, lam, events = aws_clients["iam"], aws_clients["lam"], aws_clients["events"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))

    _wire_crons(events, lam, "my-fn", "my-fn", fn_arn, {"daily": "rate(1 day)"})
    _wire_crons(events, lam, "my-fn", "my-fn", fn_arn, {"weekly": "rate(7 days)"})

    rules = {r["Name"] for r in events.list_rules(NamePrefix="my-fn-cron-")["Rules"]}
    assert rules == {"my-fn-cron-weekly"}


def test_wire_crons_is_idempotent(aws_clients, tmp_path):
    iam, lam, events = aws_clients["iam"], aws_clients["lam"], aws_clients["events"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _wire_crons(events, lam, "my-fn", "my-fn", fn_arn, {"daily": "rate(1 day)"})
    _wire_crons(events, lam, "my-fn", "my-fn", fn_arn, {"daily": "rate(1 day)"})
    assert len(events.list_rules(NamePrefix="my-fn-cron-")["Rules"]) == 1


# ---------------------------------------------------------------------------
# deploy / destroy integration
# ---------------------------------------------------------------------------


@mock_aws
def test_deploy_creates_function_and_returns_url(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    url = deploy(**_base_deploy_kwargs(deploy_patches))
    assert url
    lam = boto3.client("lambda", region_name=REGION)
    exists, _ = _function_exists(lam, "my-bot")
    assert exists


@mock_aws
def test_deploy_is_idempotent(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    kwargs = _base_deploy_kwargs(deploy_patches)
    url1 = deploy(**kwargs)
    url2 = deploy(**kwargs)
    assert url1 == url2


@mock_aws
def test_deploy_creates_worker_when_configured(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, defer_worker="my-bot-worker"))
    lam = boto3.client("lambda", region_name=REGION)
    exists, _ = _function_exists(lam, "my-bot-worker")
    assert exists


@mock_aws
def test_deploy_sets_worker_env_var_on_main_function(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, defer_worker="my-bot-worker"))
    lam = boto3.client("lambda", region_name=REGION)
    env_vars = lam.get_function_configuration(FunctionName="my-bot").get("Environment", {}).get("Variables", {})
    assert env_vars.get("CORDLESS_WORKER_FUNCTION") == "my-bot-worker"


@mock_aws
def test_deploy_worker_has_zero_retry_attempts(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, defer_worker="my-bot-worker"))
    lam = boto3.client("lambda", region_name=REGION)
    config = lam.get_function_event_invoke_config(FunctionName="my-bot-worker")
    assert config["MaximumRetryAttempts"] == 0


@mock_aws
def test_deploy_wires_crons(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, crons={"daily": "rate(1 day)"}))
    events = boto3.client("events", region_name=REGION)
    rules = events.list_rules(NamePrefix="my-bot-cron-")["Rules"]
    assert any(r["Name"] == "my-bot-cron-daily" for r in rules)


@mock_aws
def test_deploy_removes_stale_cron_rules_when_last_cron_is_deleted(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, crons={"daily": "rate(1 day)"}))
    deploy(**_base_deploy_kwargs(deploy_patches, crons={}))
    events = boto3.client("events", region_name=REGION)
    rules = events.list_rules(NamePrefix="my-bot-cron-")["Rules"]
    assert rules == []


@mock_aws
def test_deploy_raises_without_function_name(deploy_patches):
    with pytest.raises(SystemExit):
        deploy(**_base_deploy_kwargs(deploy_patches, function_name=""))


def test_new_layer_for_different_architectures():
    with mock_aws():
        lam = boto3.client("lambda", region_name="us-east-1")

        arn1 = _publish_cordless_layer(lam, "cordless", "3.12", architecture="x86_64")
        arn2 = _publish_cordless_layer(lam, "cordless", "3.12", architecture="arm64")

    assert arn1 != arn2


@mock_aws
def test_destroy_removes_function_and_api(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches))
    destroy("my-bot", "my-bot-role", REGION)
    lam = boto3.client("lambda", region_name=REGION)
    exists, _ = _function_exists(lam, "my-bot")
    assert not exists
    apigw = boto3.client("apigatewayv2", region_name=REGION)
    assert not any(a["Name"] == "my-bot-api" for a in apigw.get_apis()["Items"])


@mock_aws
def test_destroy_removes_iam_role(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches))
    destroy("my-bot", "my-bot-role", REGION)
    with pytest.raises(iam.exceptions.NoSuchEntityException):
        iam.get_role(RoleName="my-bot-role")


@mock_aws
def test_destroy_removes_cron_rules(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, crons={"daily": "rate(1 day)"}))
    destroy("my-bot", "my-bot-role", REGION)
    events = boto3.client("events", region_name=REGION)
    assert events.list_rules(NamePrefix="my-bot-cron-")["Rules"] == []


@mock_aws
def test_destroy_is_safe_when_nothing_exists():
    destroy("my-bot", "my-bot-role", REGION)


@mock_aws
def test_destroy_removes_worker(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, defer_worker="my-bot-worker"))
    destroy("my-bot", "my-bot-role", REGION, defer_worker="my-bot-worker")
    lam = boto3.client("lambda", region_name=REGION)
    exists, _ = _function_exists(lam, "my-bot-worker")
    assert not exists
