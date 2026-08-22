"""multipart/form-data encoding for Discord file attachments.

No boto3 dependency, unlike defer.py, since it's used on the direct
(non-deferred) response path too and must stay cheap to import there.
"""

import json
import mimetypes
import uuid


def build_multipart_body(payload, files):
    """Encode a Discord message payload plus file attachments.

    `files` is a list of (filename, bytes) tuples. Returns
    (body_bytes, content_type_header_value).
    """
    boundary = "cordless-" + uuid.uuid4().hex
    sep = f"--{boundary}\r\n".encode()

    parts = [
        sep + b'Content-Disposition: form-data; name="payload_json"\r\n'
        b"Content-Type: application/json\r\n\r\n" + json.dumps(payload).encode() + b"\r\n"
    ]
    for i, (filename, file_bytes) in enumerate(files):
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        parts.append(
            sep
            + f'Content-Disposition: form-data; name="files[{i}]"; filename="{filename}"\r\n'.encode()
            + f"Content-Type: {content_type}\r\n\r\n".encode()
            + file_bytes
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def build_form_multipart_body(fields, file_field_name, filename, file_bytes):
    """Encode a plain multipart/form-data body: simple string fields plus
    one named file part. Discord's usual attachment convention wraps
    everything in a payload_json part and numbered files[n] parts (see
    build_multipart_body above), but a handful of older, non-message
    endpoints (Create Guild Sticker's `file` field) just want ordinary form
    fields instead."""
    boundary = "cordless-" + uuid.uuid4().hex
    sep = f"--{boundary}\r\n".encode()

    parts = []
    for name, value in fields.items():
        header = f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        parts.append(sep + header + str(value).encode() + b"\r\n")

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    parts.append(
        sep
        + f'Content-Disposition: form-data; name="{file_field_name}"; filename="{filename}"\r\n'.encode()
        + f"Content-Type: {content_type}\r\n\r\n".encode()
        + file_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def parse_multipart_payload(body):
    """Extract the JSON payload_json part back out of a multipart body built
    by build_multipart_body() - the inverse operation, used by
    cordless.testing to decode a file-attachment response."""
    marker = b'name="payload_json"'
    start = body.index(marker)
    json_start = body.index(b"\r\n\r\n", start) + 4
    json_end = body.index(b"\r\n--", json_start)
    return json.loads(body[json_start:json_end])
