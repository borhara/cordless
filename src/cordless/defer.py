"""Deferred interaction support: async Lambda invoke and Discord followup webhook."""
import json
import mimetypes
import time
import uuid
from http.client import HTTPSConnection

_TIMEOUT = 10

# Pre-create the Lambda client at import time so cold-start invocations don't
# pay the boto3 initialisation cost inside Discord's 3-second response window.
try:
    import boto3 as _boto3
    _lambda_client = _boto3.client("lambda")
except ImportError:
    _lambda_client = None


_NO_DEPLOY_MSG = (
    "boto3 is required for deferred interactions.\n"
    "Install it: pip install 'cordless[deploy]'"
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
        raise RuntimeError(f"Lambda async invoke returned {resp['StatusCode']} (FunctionError: {resp.get('FunctionError')})")


def _patch(app_id, token, body, content_type):
    """PATCH the deferred @original message.

    Retries on 404 (a warm worker can outrun Discord processing the ACK)
    and on 429 (honouring retry_after).
    """
    status, body_out = 0, b""
    for attempt in range(3):
        conn = HTTPSConnection("discord.com", timeout=_TIMEOUT)
        try:
            conn.request(
                "PATCH",
                f"/api/v10/webhooks/{app_id}/{token}/messages/@original",
                body,
                {"Content-Type": content_type, "User-Agent": "cordless"},
            )
            resp = conn.getresponse()
            status = resp.status
            body_out = resp.read()
        finally:
            conn.close()

        if status == 404 and attempt < 2:
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
        print(f"[cordless] followup PATCH {status}: {body_out.decode(errors='replace')}")
    return status, body_out


def patch_followup(app_id, token, payload):
    return _patch(app_id, token, json.dumps(payload).encode(), "application/json")


def patch_followup_with_files(app_id, token, payload, files):
    """PATCH the deferred interaction message with file attachments.

    `files` is a list of (filename, bytes) tuples; content types are guessed
    from the filename extension.
    """
    boundary = "cordless-" + uuid.uuid4().hex
    sep = f"--{boundary}\r\n".encode()

    parts = [
        sep +
        b'Content-Disposition: form-data; name="payload_json"\r\n'
        b'Content-Type: application/json\r\n\r\n' +
        json.dumps(payload).encode() +
        b"\r\n"
    ]
    for i, (filename, file_bytes) in enumerate(files):
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        parts.append(
            sep +
            f'Content-Disposition: form-data; name="files[{i}]"; filename="{filename}"\r\n'.encode() +
            f'Content-Type: {content_type}\r\n\r\n'.encode() +
            file_bytes +
            b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    return _patch(app_id, token, body, f"multipart/form-data; boundary={boundary}")


def patch_followup_with_file(app_id, token, payload, filename, file_bytes, content_type=None):
    """Back-compat single-file wrapper around patch_followup_with_files."""
    return patch_followup_with_files(app_id, token, payload, [(filename, file_bytes)])


def post_followup(app_id, token, payload):
    """POST a new followup message (creates an additional message, does not replace @original)."""
    conn = HTTPSConnection("discord.com", timeout=_TIMEOUT)
    try:
        conn.request(
            "POST",
            f"/api/v10/webhooks/{app_id}/{token}",
            json.dumps(payload).encode(),
            {"Content-Type": "application/json", "User-Agent": "cordless"},
        )
        resp = conn.getresponse()
        status = resp.status
        body = resp.read()
    finally:
        conn.close()
    if status >= 300:
        print(f"[cordless] followup POST {status}: {body.decode(errors='replace')}")
    return status, body


def delete_original(app_id, token):
    """DELETE the deferred @original message."""
    conn = HTTPSConnection("discord.com", timeout=_TIMEOUT)
    try:
        conn.request(
            "DELETE",
            f"/api/v10/webhooks/{app_id}/{token}/messages/@original",
            None,
            {"User-Agent": "cordless"},
        )
        resp = conn.getresponse()
        status = resp.status
        resp.read()
    finally:
        conn.close()
    return status
