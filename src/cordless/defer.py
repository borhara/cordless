"""Deferred interaction support — async Lambda invoke and Discord followup webhook."""
import json
from http.client import HTTPSConnection


def invoke_worker(function_name, interaction):
    import boto3
    boto3.client("lambda").invoke(
        FunctionName=function_name,
        InvocationType="Event",
        Payload=json.dumps(interaction).encode(),
    )


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
        print(f"[cordless] followup PATCH app_id={app_id} token={token[:20]}... → {status}")
        if status >= 300:
            print(f"[cordless] followup body: {body_out.decode(errors='replace')}")
        return status, body_out
    finally:
        conn.close()
