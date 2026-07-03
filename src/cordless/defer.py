"""Deferred interaction support — async Lambda invoke and Discord followup webhook."""
import json
from http.client import HTTPSConnection

# Pre-create the Lambda client at import time so cold-start invocations don't
# pay the boto3 initialisation cost inside Discord's 3-second response window.
try:
    import boto3 as _boto3
    _lambda_client = _boto3.client("lambda")
except ImportError:
    _lambda_client = None


def invoke_worker(function_name, interaction):
    client = _lambda_client
    if client is None:
        import boto3
        client = boto3.client("lambda")
    resp = client.invoke(
        FunctionName=function_name,
        InvocationType="Event",
        Payload=json.dumps(interaction).encode(),
    )
    if resp["StatusCode"] != 202:
        raise RuntimeError(f"Lambda async invoke returned {resp['StatusCode']} (FunctionError: {resp.get('FunctionError')})")


def patch_followup(app_id, token, payload):
    body = json.dumps(payload).encode()
    conn = HTTPSConnection("discord.com")
    try:
        conn.request(
            "PATCH",
            f"/api/v10/webhooks/{app_id}/{token}/messages/@original",
            body,
            {"Content-Type": "application/json", "User-Agent": "cordless"},
        )
        resp = conn.getresponse()
        status = resp.status
        body_out = resp.read()
        if status >= 300:
            print(f"[cordless] followup PATCH {status}: {body_out.decode(errors='replace')}")
        return status, body_out
    finally:
        conn.close()
