"""Deferred interaction support — SQS push and Discord followup webhook."""
import json
from http.client import HTTPSConnection


def push_to_queue(queue_url, interaction):
    import boto3
    boto3.client("sqs").send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(interaction),
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
        return resp.status, resp.read()
    finally:
        conn.close()
