"""Deferred interaction support: async Lambda invoke and Discord followup webhook."""

import json
import threading
import time
from http.client import HTTPException, HTTPSConnection

_TIMEOUT = 10

# Kept open across invocations in a warm Lambda container, so most requests
# skip the TLS handshake instead of paying for it every time.
_conn = None
_conn_lock = threading.Lock()


def _send(method, path, body, headers):
    global _conn
    with _conn_lock:
        if _conn is None:
            _conn = HTTPSConnection("discord.com", timeout=_TIMEOUT)
        try:
            _conn.request(method, path, body, headers)
            resp = _conn.getresponse()
            return resp.status, resp.read()
        except (HTTPException, OSError):
            # the other end closed the kept-alive connection, reconnect once
            _conn.close()
            _conn = HTTPSConnection("discord.com", timeout=_TIMEOUT)
            _conn.request(method, path, body, headers)
            resp = _conn.getresponse()
            return resp.status, resp.read()


# Pre-create the Lambda client at import time so cold-start invocations don't
# pay the boto3 initialisation cost inside Discord's 3-second response window.
try:
    import boto3 as _boto3
    from botocore.exceptions import NoRegionError as _NoRegionError

    try:
        _lambda_client = _boto3.client("lambda")
    except _NoRegionError:
        _lambda_client = None
except ImportError:
    _lambda_client = None


_NO_DEPLOY_MSG = (
    "boto3 is required for deferred interactions but isn't installed. It ships with "
    "cordless itself; try: pip install --force-reinstall cordless"
)


def invoke_worker(function_name, interaction):
    client = _lambda_client
    if client is None:
        try:
            import boto3

            client = boto3.client("lambda")
        except ImportError:
            raise RuntimeError(_NO_DEPLOY_MSG)
    resp = client.invoke(
        FunctionName=function_name,
        InvocationType="Event",
        Payload=json.dumps(interaction).encode(),
    )
    if resp["StatusCode"] != 202:
        raise RuntimeError(
            f"Lambda async invoke returned {resp['StatusCode']} (FunctionError: {resp.get('FunctionError')})"
        )


def _request(method, path, body=None, content_type=None, retry_404=False):
    """Make a webhooks/{app_id}/{token}/... call.

    Retries on 429 (honouring retry_after) always, and on 404 (a warm worker
    can outrun Discord processing the ACK for @original) when retry_404 is
    set. Each interaction has its own token, which Discord uses as the
    bucket's major parameter for these routes, so calls here essentially
    never share a bucket with another invocation or with send_message's
    channel buckets - there's nothing for the cross-invocation coordination
    in ratelimit.py to usefully do here, just a local retry.
    """
    headers = {"User-Agent": "cordless"}
    if content_type:
        headers["Content-Type"] = content_type

    status, body_out = 0, b""
    for attempt in range(3):
        status, body_out = _send(method, path, body, headers)

        if status == 404 and retry_404 and attempt < 2:
            time.sleep(0.5)
            continue
        if status == 429 and attempt < 2:
            try:
                retry_after = float(json.loads(body_out).get("retry_after", 1))
            except (ValueError, AttributeError):
                retry_after = 1.0
            time.sleep(min(retry_after, 5))
            continue
        break

    if status >= 300:
        print(f"[cordless] {method} {path} {status}: {body_out.decode(errors='replace')}")
    return status, body_out


def patch_followup(app_id, token, payload):
    return _request(
        "PATCH",
        f"/api/v10/webhooks/{app_id}/{token}/messages/@original",
        json.dumps(payload).encode(),
        "application/json",
        retry_404=True,
    )


def patch_followup_with_files(app_id, token, payload, files):
    """PATCH the deferred interaction message with file attachments.

    `files` is a list of (filename, bytes) tuples; content types are guessed
    from the filename extension.
    """
    from ._multipart import build_multipart_body

    body, content_type = build_multipart_body(payload, files)
    return _request(
        "PATCH", f"/api/v10/webhooks/{app_id}/{token}/messages/@original", body, content_type, retry_404=True
    )


def patch_followup_with_file(app_id, token, payload, filename, file_bytes, content_type=None):
    """Back-compat single-file wrapper around patch_followup_with_files."""
    return patch_followup_with_files(app_id, token, payload, [(filename, file_bytes)])


def post_followup(app_id, token, payload):
    """POST a new followup message (creates an additional message, does not replace @original)."""
    return _request("POST", f"/api/v10/webhooks/{app_id}/{token}", json.dumps(payload).encode(), "application/json")


def delete_original(app_id, token):
    """DELETE the deferred @original message."""
    status, _ = _request("DELETE", f"/api/v10/webhooks/{app_id}/{token}/messages/@original", retry_404=True)
    return status
