"""Local header tracking + DynamoDB fallback for outbound rate-limit coordination."""

import os
import random

import boto3
import pytest
from moto import mock_aws

import cordless.ratelimit as ratelimit

REGION = "us-east-1"
TABLE = "my-bot-ratelimit"

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", REGION)


@pytest.fixture(autouse=True)
def _reset_local_cache():
    ratelimit._local.clear()
    yield
    ratelimit._local.clear()


def test_jittered_wait_stays_within_half_to_full_of_the_capped_value():
    for _ in range(200):
        result = ratelimit.jittered_wait(2.0)
        assert 1.0 <= result <= 2.0


def test_jittered_wait_caps_at_max_wait_before_jittering():
    for _ in range(200):
        result = ratelimit.jittered_wait(100.0)
        assert ratelimit._MAX_WAIT / 2 <= result <= ratelimit._MAX_WAIT


def test_disabled_without_table_env_var(monkeypatch):
    monkeypatch.delenv(ratelimit._TABLE_ENV_VAR, raising=False)
    assert ratelimit.enabled() is False


def test_enabled_with_table_env_var(monkeypatch):
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, TABLE)
    assert ratelimit.enabled() is True


def test_record_response_noop_when_disabled(monkeypatch):
    monkeypatch.delenv(ratelimit._TABLE_ENV_VAR, raising=False)
    headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset-After": "5"}
    ratelimit.record_response("POST", "/channels/1/messages", headers)
    assert ratelimit._local == {}


def test_record_response_caches_remaining_and_reset(monkeypatch):
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, TABLE)
    ratelimit.record_response(
        "POST", "/channels/1/messages", {"X-RateLimit-Remaining": "3", "X-RateLimit-Reset-After": "2.5"}
    )
    remaining, reset_at = ratelimit._local["POST /channels/1/messages"]
    assert remaining == 3
    import time

    assert reset_at > time.time()


def test_record_response_ignores_missing_headers(monkeypatch):
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, TABLE)
    ratelimit.record_response("POST", "/channels/1/messages", {})
    assert ratelimit._local == {}


def test_wait_if_needed_skips_dynamo_when_locally_clear(monkeypatch):
    """Plenty of remaining budget locally - never touches DynamoDB."""
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, TABLE)
    monkeypatch.setattr(ratelimit, "_shared_block", lambda key: (_ for _ in ()).throw(AssertionError("should not run")))
    ratelimit.record_response(
        "POST", "/channels/1/messages", {"X-RateLimit-Remaining": "5", "X-RateLimit-Reset-After": "5"}
    )
    ratelimit.wait_if_needed("POST", "/channels/1/messages")  # would raise if it touched _shared_block


def test_wait_if_needed_checks_dynamo_on_cold_start(monkeypatch):
    """No local cache at all - has to ask the shared table."""
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, TABLE)
    calls = []
    monkeypatch.setattr(ratelimit, "_shared_block", lambda key: calls.append(key) or None)
    ratelimit.wait_if_needed("POST", "/channels/1/messages")
    assert calls == ["POST /channels/1/messages"]


def test_wait_if_needed_sleeps_on_local_state_even_if_shared_check_fails(monkeypatch):
    """A local note_blocked() must still cause a wait even when DynamoDB is
    unreachable/unconfigured and _shared_block fails open to None - otherwise
    concurrent callers in the same process get zero benefit from each other's
    429s whenever the shared table isn't actually working."""
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, TABLE)
    import time

    monkeypatch.setattr(ratelimit, "_shared_block", lambda key: None)
    monkeypatch.setattr(ratelimit, "_put_shared", lambda key, blocked_until: None)
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    ratelimit.note_blocked("POST", "/channels/1/messages", 0.3)
    ratelimit.wait_if_needed("POST", "/channels/1/messages")

    assert slept and slept[0] <= ratelimit._MAX_WAIT


def test_wait_if_needed_prefers_the_later_of_local_and_shared_block(monkeypatch):
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, TABLE)
    import time

    now = time.time()
    ratelimit._local["POST /channels/1/messages"] = (0, now + 0.1)
    monkeypatch.setattr(ratelimit, "_shared_block", lambda key: now + 10)
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    monkeypatch.setattr(random, "uniform", lambda a, b: b)  # deterministic: always the top of the jitter range

    ratelimit.wait_if_needed("POST", "/channels/1/messages")

    # the shared block (now+10) wins over local (now+0.1), then gets capped at
    # _MAX_WAIT before jitter is applied - so the full jittered range caps at _MAX_WAIT
    assert slept and slept[0] == pytest.approx(ratelimit._MAX_WAIT)


def test_wait_if_needed_sleeps_until_shared_block_clears(monkeypatch):
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, TABLE)
    import time

    monkeypatch.setattr(ratelimit, "_shared_block", lambda key: time.time() + 0.05)
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
    ratelimit.wait_if_needed("POST", "/channels/1/messages")
    assert slept and slept[0] <= ratelimit._MAX_WAIT


def test_note_blocked_writes_local_and_shared_state(monkeypatch):
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, TABLE)
    written = []
    monkeypatch.setattr(ratelimit, "_put_shared", lambda key, blocked_until: written.append((key, blocked_until)))
    ratelimit.note_blocked("POST", "/channels/1/messages", 2.0)
    assert ratelimit._local["POST /channels/1/messages"][0] == 0
    assert written and written[0][0] == "POST /channels/1/messages"


@pytest.fixture
def dynamo_table(monkeypatch):
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, TABLE)
    with mock_aws():
        dynamodb = boto3.client("dynamodb", region_name=REGION)
        dynamodb.create_table(
            TableName=TABLE,
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb.get_waiter("table_exists").wait(TableName=TABLE)
        yield


def test_shared_roundtrip_through_real_dynamo(dynamo_table):
    import time

    blocked_until = time.time() + 10
    ratelimit._put_shared("POST /channels/1/messages", blocked_until)
    assert ratelimit._shared_block("POST /channels/1/messages") == int(blocked_until) + 1
    assert ratelimit._shared_block("POST /channels/2/messages") is None


def test_shared_block_is_a_plain_float_not_decimal(dynamo_table):
    """boto3's resource API deserializes DynamoDB Numbers as decimal.Decimal, which
    blows up when wait_if_needed subtracts a float time.time() from it. Regression
    test for that - assert the type, not just the value, so a mocked-only shared
    return can't hide it again."""
    import time

    ratelimit._put_shared("POST /channels/1/messages", time.time() + 10)
    result = ratelimit._shared_block("POST /channels/1/messages")
    assert isinstance(result, float)
    result - time.time()  # would raise TypeError if this were still a Decimal


def test_wait_if_needed_works_end_to_end_against_real_dynamo(dynamo_table, monkeypatch):
    """The actual bug: wait_if_needed's blocked_until - time.time() raised
    TypeError against a real DynamoDB-backed table because _shared_block
    returned a Decimal, never caught by tests that monkeypatched _shared_block
    to return plain floats instead of exercising a real table round-trip."""
    import time

    monkeypatch.setattr(random, "uniform", lambda a, b: a)
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    ratelimit._put_shared("POST /channels/1/messages", time.time() + 0.2)
    ratelimit.wait_if_needed("POST", "/channels/1/messages")  # would raise TypeError pre-fix

    assert slept


def test_shared_block_fails_open_when_table_missing(monkeypatch):
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, "does-not-exist")
    with mock_aws():
        assert ratelimit._shared_block("POST /channels/1/messages") is None


def test_put_shared_fails_open_when_table_missing(monkeypatch):
    monkeypatch.setenv(ratelimit._TABLE_ENV_VAR, "does-not-exist")
    with mock_aws():
        ratelimit._put_shared("POST /channels/1/messages", 123)  # should not raise
