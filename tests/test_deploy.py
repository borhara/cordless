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
    _ensure_function_url,
    _function_exists,
    _health_check,
    _publish_cordless_layer,
    _remove_keepwarm,
    _wire_crons,
    _wire_keepwarm,
    deploy,
    destroy,
    ensure_iam_role,
    ensure_ratelimit_table,
    ratelimit_table_name,
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


def test_ensure_function_url_creates_url(aws_clients, tmp_path):
    iam, lam = aws_clients["iam"], aws_clients["lam"]
    role_arn = _make_role(iam)
    _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    url = _ensure_function_url(lam, "my-fn")
    assert url
    assert lam.get_function_url_config(FunctionName="my-fn")["FunctionUrl"] == url


def test_ensure_function_url_is_idempotent(aws_clients, tmp_path):
    iam, lam = aws_clients["iam"], aws_clients["lam"]
    role_arn = _make_role(iam)
    _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    url1 = _ensure_function_url(lam, "my-fn")
    url2 = _ensure_function_url(lam, "my-fn")
    assert url1 == url2


def test_ensure_function_url_grants_both_required_permission_statements(aws_clients, tmp_path):
    """AWS requires two resource-policy statements for a public (AuthType=NONE)
    function URL, not one - lambda:InvokeFunctionUrl, and (since October 2025)
    a second lambda:InvokeFunction statement gated on InvokedViaFunctionUrl.
    Without the second one every request 403s before it reaches the handler,
    which is what silently broke Discord's endpoint verification."""
    iam, lam = aws_clients["iam"], aws_clients["lam"]
    role_arn = _make_role(iam)
    _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _ensure_function_url(lam, "my-fn")

    policy = json.loads(lam.get_policy(FunctionName="my-fn")["Policy"])
    actions = {stmt["Action"] for stmt in policy["Statement"]}
    assert "lambda:InvokeFunctionUrl" in actions
    assert "lambda:InvokeFunction" in actions

    # moto represents InvokedViaFunctionUrl as a flat statement key rather than
    # the real Condition:{Bool:{lambda:InvokedViaFunctionUrl}} shape AWS uses,
    # so this checks moto's shape - the real shape was verified by hand against
    # live AWS, which is what actually confirmed the fix
    invoke_function_stmt = next(s for s in policy["Statement"] if s["Action"] == "lambda:InvokeFunction")
    assert invoke_function_stmt.get("InvokedViaFunctionUrl") is True


def test_ensure_function_url_heals_missing_permission_on_existing_url(aws_clients, tmp_path):
    """A function whose URL config was created by an older cordless version (or
    a partially failed earlier deploy) may already have the URL but be missing
    the lambda:InvokeFunction statement. Calling _ensure_function_url again -
    e.g. on a routine redeploy - must add the missing statement, not skip
    straight past it because the URL config already exists."""
    iam, lam = aws_clients["iam"], aws_clients["lam"]
    role_arn = _make_role(iam)
    _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))

    # simulate the old, incomplete setup: URL config + only the first statement
    lam.create_function_url_config(FunctionName="my-fn", AuthType="NONE")
    lam.add_permission(
        FunctionName="my-fn",
        StatementId="FunctionURLAllowPublicAccess",
        Action="lambda:InvokeFunctionUrl",
        Principal="*",
        FunctionUrlAuthType="NONE",
    )
    policy = json.loads(lam.get_policy(FunctionName="my-fn")["Policy"])
    assert {s["Action"] for s in policy["Statement"]} == {"lambda:InvokeFunctionUrl"}

    _ensure_function_url(lam, "my-fn")

    policy = json.loads(lam.get_policy(FunctionName="my-fn")["Policy"])
    actions = {stmt["Action"] for stmt in policy["Statement"]}
    assert actions == {"lambda:InvokeFunctionUrl", "lambda:InvokeFunction"}


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
# _wire_keepwarm / _remove_keepwarm
# ---------------------------------------------------------------------------


def test_wire_keepwarm_creates_rule_targeting_main(aws_clients, tmp_path):
    """The whole point: this must always target the main function directly,
    never a defer_worker - regular crons can't do that, since they all share
    one target."""
    iam, lam, events = aws_clients["iam"], aws_clients["lam"], aws_clients["events"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _wire_keepwarm(events, lam, "my-fn", fn_arn, True)

    rules = events.list_rules(NamePrefix="my-fn-keepwarm")["Rules"]
    assert len(rules) == 1
    assert rules[0]["ScheduleExpression"] == "rate(5 minutes)"
    targets = events.list_targets_by_rule(Rule="my-fn-keepwarm")["Targets"]
    assert targets[0]["Arn"] == fn_arn
    assert json.loads(targets[0]["Input"]) == {"_cordless_keepwarm": True}


def test_wire_keepwarm_accepts_custom_schedule(aws_clients, tmp_path):
    iam, lam, events = aws_clients["iam"], aws_clients["lam"], aws_clients["events"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _wire_keepwarm(events, lam, "my-fn", fn_arn, "rate(10 minutes)")

    rules = events.list_rules(NamePrefix="my-fn-keepwarm")["Rules"]
    assert rules[0]["ScheduleExpression"] == "rate(10 minutes)"


def test_wire_keepwarm_is_idempotent(aws_clients, tmp_path):
    iam, lam, events = aws_clients["iam"], aws_clients["lam"], aws_clients["events"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _wire_keepwarm(events, lam, "my-fn", fn_arn, True)
    _wire_keepwarm(events, lam, "my-fn", fn_arn, True)
    assert len(events.list_rules(NamePrefix="my-fn-keepwarm")["Rules"]) == 1


def test_wire_keepwarm_false_removes_existing_rule(aws_clients, tmp_path):
    iam, lam, events = aws_clients["iam"], aws_clients["lam"], aws_clients["events"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _wire_keepwarm(events, lam, "my-fn", fn_arn, True)
    _wire_keepwarm(events, lam, "my-fn", fn_arn, None)
    assert events.list_rules(NamePrefix="my-fn-keepwarm")["Rules"] == []


def test_remove_keepwarm_is_safe_when_nothing_exists(aws_clients, tmp_path):
    iam, lam, events = aws_clients["iam"], aws_clients["lam"], aws_clients["events"]
    role_arn = _make_role(iam)
    _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _remove_keepwarm(events, lam, "my-fn")  # must not raise


# ---------------------------------------------------------------------------
# _health_check (describe-only, no AWS cost)
# ---------------------------------------------------------------------------


def test_health_check_all_green_when_everything_is_wired_correctly(aws_clients, tmp_path):
    iam, lam, apigw, events = aws_clients["iam"], aws_clients["lam"], aws_clients["apigw"], aws_clients["events"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _ensure_function_url(lam, "my-fn")
    _wire_crons(events, lam, "my-fn", "my-fn", fn_arn, {"daily": "rate(1 day)"})
    _wire_keepwarm(events, lam, "my-fn", fn_arn, True)

    checks = _health_check(
        lam, apigw, events, None, "my-fn", None, "function_url", {"daily": "rate(1 day)"}, True, False, None
    )

    assert checks
    assert all(ok for ok, _, _ in checks)


def test_health_check_flags_missing_function_url_permission_statement(aws_clients, tmp_path):
    """Regression test for the actual bug this session found: a Function URL
    with only the lambda:InvokeFunctionUrl statement, missing the second
    lambda:InvokeFunction one, looks fine until a real request 403s."""
    iam, lam, apigw, events = aws_clients["iam"], aws_clients["lam"], aws_clients["apigw"], aws_clients["events"]
    role_arn = _make_role(iam)
    _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    lam.create_function_url_config(FunctionName="my-fn", AuthType="NONE")
    lam.add_permission(
        FunctionName="my-fn",
        StatementId="FunctionURLAllowPublicAccess",
        Action="lambda:InvokeFunctionUrl",
        Principal="*",
        FunctionUrlAuthType="NONE",
    )

    checks = _health_check(lam, apigw, events, None, "my-fn", None, "function_url", None, False, False, None)

    label_map = {label: (ok, detail) for ok, label, detail in checks}
    assert label_map["Function URL permissions"][0] is False


def test_health_check_flags_missing_cron_rule(aws_clients, tmp_path):
    iam, lam, apigw, events = aws_clients["iam"], aws_clients["lam"], aws_clients["apigw"], aws_clients["events"]
    role_arn = _make_role(iam)
    _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    # note: never actually wired via _wire_crons

    checks = _health_check(
        lam, apigw, events, None, "my-fn", None, "function_url", {"daily": "rate(1 day)"}, False, False, None
    )

    label_map = {label: (ok, detail) for ok, label, detail in checks}
    ok, detail = label_map["Cron rules"]
    assert ok is False
    assert "daily" in detail


def test_health_check_flags_keepwarm_targeting_wrong_function(aws_clients, tmp_path):
    """Mirrors the earlier bug where a hand-rolled keep-warm cron ended up
    also wired to the worker via the normal cron path - a keep-warm rule is
    only useful if it targets the main function."""
    iam, lam, apigw, events = aws_clients["iam"], aws_clients["lam"], aws_clients["apigw"], aws_clients["events"]
    role_arn = _make_role(iam)
    _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    wrong_arn = _make_function(lam, "my-fn-worker", role_arn, _minimal_zip(tmp_path))
    _wire_keepwarm(events, lam, "my-fn", wrong_arn, True)

    checks = _health_check(lam, apigw, events, None, "my-fn", None, "function_url", None, True, False, None)

    label_map = {label: (ok, detail) for ok, label, detail in checks}
    assert label_map["Keep-warm rule"][0] is False


def test_health_check_reports_api_gateway_endpoint(aws_clients, tmp_path):
    iam, lam, apigw, events = aws_clients["iam"], aws_clients["lam"], aws_clients["apigw"], aws_clients["events"]
    role_arn = _make_role(iam)
    fn_arn = _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    _ensure_api_gateway(apigw, lam, "my-fn", fn_arn, REGION, ACCOUNT_ID)

    checks = _health_check(lam, apigw, events, None, "my-fn", None, "api_gateway", None, False, False, None)

    label_map = {label: (ok, detail) for ok, label, detail in checks}
    assert label_map["API Gateway"][0] is True


def test_health_check_reports_ratelimit_table_status(aws_clients, tmp_path):
    iam, lam, apigw, events = aws_clients["iam"], aws_clients["lam"], aws_clients["apigw"], aws_clients["events"]
    dynamodb = boto3.client("dynamodb", region_name=REGION)
    role_arn = _make_role(iam)
    _make_function(lam, "my-fn", role_arn, _minimal_zip(tmp_path))
    table_name = ratelimit_table_name("my-fn")
    ensure_ratelimit_table(dynamodb, table_name)

    checks = _health_check(
        lam, apigw, events, dynamodb, "my-fn", None, "function_url", None, False, True, table_name
    )

    label_map = {label: (ok, detail) for ok, label, detail in checks}
    assert label_map["Rate limit table"] == (True, "ACTIVE")


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
def test_deploy_warns_when_pynacl_bundle_failed(deploy_patches, monkeypatch, capsys):
    import cordless.upload

    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    cordless.upload.pynacl_bundle_failed = False

    def _fresh_zip_with_pynacl_failure(*a, **kw):
        cordless.upload.pynacl_bundle_failed = True
        return _minimal_zip(deploy_patches)

    monkeypatch.setattr(cordless.deploy, "build_function_zip", _fresh_zip_with_pynacl_failure)

    url = deploy(**_base_deploy_kwargs(deploy_patches))

    assert url  # deploy must still succeed, not raise
    out = capsys.readouterr().out
    assert "Signature verification: pure-Python Ed25519 (slower than pynacl)" in out
    assert "⚠" in out


@mock_aws
def test_deploy_summary_shows_pynacl_when_bundled(deploy_patches, monkeypatch, capsys):
    import cordless.upload

    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    cordless.upload.pynacl_bundle_failed = False

    deploy(**_base_deploy_kwargs(deploy_patches))

    out = capsys.readouterr().out
    assert "Signature verification: pynacl" in out
    assert "✓" in out


@mock_aws
def test_deploy_summary_shows_runtime(deploy_patches, monkeypatch, capsys):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))

    deploy(**_base_deploy_kwargs(deploy_patches, runtime="python3.13"))

    out = capsys.readouterr().out
    assert "Runtime: python3.13" in out


@mock_aws
def test_deploy_summary_includes_health_check(deploy_patches, monkeypatch, capsys):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))

    deploy(**_base_deploy_kwargs(deploy_patches, keep_warm=True, crons={"daily": "rate(1 day)"}))

    out = capsys.readouterr().out
    assert "Function: Active" in out
    assert "Function URL permissions: both required statements present" in out
    assert "Cron rules: all present" in out
    assert "Keep-warm rule: targets main function" in out


@mock_aws
def test_deploy_defaults_new_function_to_arm64(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches))
    lam = boto3.client("lambda", region_name=REGION)
    config = lam.get_function_configuration(FunctionName="my-bot")
    assert config["Architectures"] == ["arm64"]


@mock_aws
def test_deploy_keeps_existing_architecture_when_unspecified(deploy_patches, monkeypatch):
    """AWS won't let an existing function's architecture change in place, so a
    redeploy that doesn't ask for a specific architecture must not try to flip it."""
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    kwargs = _base_deploy_kwargs(deploy_patches)
    deploy(**kwargs, architecture="x86_64")
    deploy(**kwargs)  # no architecture given this time
    lam = boto3.client("lambda", region_name=REGION)
    config = lam.get_function_configuration(FunctionName="my-bot")
    assert config["Architectures"] == ["x86_64"]


@mock_aws
def test_deploy_explicit_architecture_always_wins(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, architecture="x86_64"))
    lam = boto3.client("lambda", region_name=REGION)
    config = lam.get_function_configuration(FunctionName="my-bot")
    assert config["Architectures"] == ["x86_64"]


@mock_aws
def test_deploy_defaults_new_function_to_function_url(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches))
    lam = boto3.client("lambda", region_name=REGION)
    config = lam.get_function_url_config(FunctionName="my-bot")
    assert config["FunctionUrl"]


@mock_aws
def test_deploy_keeps_existing_api_gateway_when_unspecified(deploy_patches, monkeypatch):
    """A redeploy that doesn't ask for a specific endpoint must not silently
    switch an existing API Gateway deployment over to a Function URL."""
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    kwargs = _base_deploy_kwargs(deploy_patches)
    deploy(**kwargs, endpoint="api_gateway")
    deploy(**kwargs)  # no endpoint given this time
    lam = boto3.client("lambda", region_name=REGION)
    with pytest.raises(lam.exceptions.ResourceNotFoundException):
        lam.get_function_url_config(FunctionName="my-bot")
    apigw = boto3.client("apigatewayv2", region_name=REGION)
    apis = apigw.get_apis()["Items"]
    assert any(a["Name"] == "my-bot-api" for a in apis)


@mock_aws
def test_deploy_keeps_existing_function_url_when_unspecified(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    kwargs = _base_deploy_kwargs(deploy_patches)
    deploy(**kwargs, endpoint="function_url")
    deploy(**kwargs)  # no endpoint given this time
    lam = boto3.client("lambda", region_name=REGION)
    config = lam.get_function_url_config(FunctionName="my-bot")
    assert config["FunctionUrl"]


@mock_aws
def test_deploy_explicit_endpoint_always_wins(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, endpoint="api_gateway"))
    lam = boto3.client("lambda", region_name=REGION)
    with pytest.raises(lam.exceptions.ResourceNotFoundException):
        lam.get_function_url_config(FunctionName="my-bot")


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
def test_deploy_keepwarm_targets_main_even_with_defer_worker(deploy_patches, monkeypatch):
    """The whole reason this feature exists: regular crons all go to
    defer_worker when it's set, leaving the main function - the one every
    Discord interaction hits first - with nothing keeping it warm."""
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(
        **_base_deploy_kwargs(
            deploy_patches,
            defer_worker="my-bot-worker",
            crons={"daily": "rate(1 day)"},
            keep_warm=True,
        )
    )
    lam = boto3.client("lambda", region_name=REGION)
    events = boto3.client("events", region_name=REGION)

    main_arn = lam.get_function_configuration(FunctionName="my-bot")["FunctionArn"]
    targets = events.list_targets_by_rule(Rule="my-bot-keepwarm")["Targets"]
    assert targets[0]["Arn"] == main_arn

    # the regular cron, meanwhile, still goes to the worker as usual
    worker_arn = lam.get_function_configuration(FunctionName="my-bot-worker")["FunctionArn"]
    cron_targets = events.list_targets_by_rule(Rule="my-bot-cron-daily")["Targets"]
    assert cron_targets[0]["Arn"] == worker_arn


@mock_aws
def test_deploy_without_keepwarm_does_not_create_a_rule(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches))
    events = boto3.client("events", region_name=REGION)
    assert events.list_rules(NamePrefix="my-bot-keepwarm")["Rules"] == []


@mock_aws
def test_destroy_removes_keepwarm_rule(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, keep_warm=True))
    destroy(function_name="my-bot", role_name="my-bot-role", region=REGION)
    events = boto3.client("events", region_name=REGION)
    assert events.list_rules(NamePrefix="my-bot-keepwarm")["Rules"] == []


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


# ---------------------------------------------------------------------------
# Rate limit table
# ---------------------------------------------------------------------------


@mock_aws
def test_ensure_ratelimit_table_creates_table():
    dynamodb = boto3.client("dynamodb", region_name=REGION)
    ensure_ratelimit_table(dynamodb, "my-bot-ratelimit")
    assert dynamodb.describe_table(TableName="my-bot-ratelimit")["Table"]["TableStatus"] == "ACTIVE"


@mock_aws
def test_ensure_ratelimit_table_is_idempotent():
    dynamodb = boto3.client("dynamodb", region_name=REGION)
    ensure_ratelimit_table(dynamodb, "my-bot-ratelimit")
    ensure_ratelimit_table(dynamodb, "my-bot-ratelimit")  # would raise if it tried to re-create


@mock_aws
def test_deploy_creates_ratelimit_table_when_enabled(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, ratelimit=True))
    dynamodb = boto3.client("dynamodb", region_name=REGION)
    assert dynamodb.describe_table(TableName="my-bot-ratelimit")["Table"]["TableStatus"] == "ACTIVE"


@mock_aws
def test_deploy_skips_ratelimit_table_when_disabled(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches))
    dynamodb = boto3.client("dynamodb", region_name=REGION)
    with pytest.raises(dynamodb.exceptions.ResourceNotFoundException):
        dynamodb.describe_table(TableName="my-bot-ratelimit")


@mock_aws
def test_deploy_sets_ratelimit_table_env_var(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, ratelimit=True))
    lam = boto3.client("lambda", region_name=REGION)
    env_vars = lam.get_function_configuration(FunctionName="my-bot").get("Environment", {}).get("Variables", {})
    assert env_vars.get("CORDLESS_RATELIMIT_TABLE") == "my-bot-ratelimit"


@mock_aws
def test_deploy_sets_ratelimit_table_env_var_on_worker_too(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, ratelimit=True, defer_worker="my-bot-worker"))
    lam = boto3.client("lambda", region_name=REGION)
    env_vars = lam.get_function_configuration(FunctionName="my-bot-worker").get("Environment", {}).get("Variables", {})
    assert env_vars.get("CORDLESS_RATELIMIT_TABLE") == "my-bot-ratelimit"


@mock_aws
def test_deploy_grants_ratelimit_table_access(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, ratelimit=True))
    policy = iam.get_role_policy(RoleName="my-bot-role", PolicyName="cordless-ratelimit-table")
    assert "dynamodb:PutItem" in policy["PolicyDocument"]["Statement"][0]["Action"]


@mock_aws
def test_deploy_is_idempotent_with_ratelimit_enabled(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    kwargs = _base_deploy_kwargs(deploy_patches, ratelimit=True)
    deploy(**kwargs)
    deploy(**kwargs)  # would raise if the table create wasn't idempotent


@mock_aws
def test_destroy_removes_ratelimit_table(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, ratelimit=True))
    destroy("my-bot", "my-bot-role", REGION, ratelimit=True)
    dynamodb = boto3.client("dynamodb", region_name=REGION)
    with pytest.raises(dynamodb.exceptions.ResourceNotFoundException):
        dynamodb.describe_table(TableName=ratelimit_table_name("my-bot"))


@mock_aws
def test_destroy_leaves_ratelimit_table_when_flag_omitted(deploy_patches, monkeypatch):
    iam = boto3.client("iam", region_name=REGION)
    monkeypatch.setattr(cordless.deploy, "_LAMBDA_BASIC_EXECUTION_POLICY", _seed_lambda_execution_policy(iam))
    deploy(**_base_deploy_kwargs(deploy_patches, ratelimit=True))
    destroy("my-bot", "my-bot-role", REGION)
    dynamodb = boto3.client("dynamodb", region_name=REGION)
    assert dynamodb.describe_table(TableName=ratelimit_table_name("my-bot"))["Table"]["TableStatus"] == "ACTIVE"


@mock_aws
def test_destroy_is_safe_when_ratelimit_table_never_existed():
    destroy("my-bot", "my-bot-role", REGION, ratelimit=True)
