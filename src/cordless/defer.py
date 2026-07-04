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


def patch_followup_with_file(app_id, token, payload, filename, file_bytes, content_type="image/png"):
    """PATCH the deferred interaction message with a file attachment."""
    boundary = "cordless_boundary_" + str(id(file_bytes))
    sep = f"--{boundary}\r\n".encode()
    end = f"--{boundary}--\r\n".encode()

    json_part = (
        sep +
        b'Content-Disposition: form-data; name="payload_json"\r\n'
        b'Content-Type: application/json\r\n\r\n' +
        json.dumps(payload).encode() +
        b"\r\n"
    )
    file_part = (
        sep +
        f'Content-Disposition: form-data; name="files[0]"; filename="{filename}"\r\n'.encode() +
        f'Content-Type: {content_type}\r\n\r\n'.encode() +
        file_bytes +
        b"\r\n"
    )
    body = json_part + file_part + end

    conn = HTTPSConnection("discord.com")
    try:
        conn.request(
            "PATCH",
            f"/api/v10/webhooks/{app_id}/{token}/messages/@original",
            body,
            {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "cordless",
            },
        )
        resp = conn.getresponse()
        status = resp.status
        body_out = resp.read()
        if status >= 300:
            print(f"[cordless] followup PATCH (file) {status}: {body_out.decode(errors='replace')}")
        return status, body_out
    finally:
        conn.close()
