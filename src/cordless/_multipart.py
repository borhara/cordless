"""multipart/form-data encoding for Discord file attachments.

No boto3 dependency, unlike defer.py, since it's used on the direct
(non-deferred) response path too and must stay cheap to import there.
"""

import json
import mimetypes
import uuid
from collections.abc import Mapping
from typing import Any


def _quote_header_value(value: object) -> str:
    """Escape a value for use inside a quoted Content-Disposition parameter.
    Strips CR/LF outright (they'd inject extra header lines or parts into
    the multipart body, not just break the current header) and backslash-
    escapes backslashes/quotes per the quoted-string syntax the other side
    is expected to parse this with."""
    value = str(value).replace("\r", "").replace("\n", "")
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_multipart_body(payload: Any, files: list[tuple[str, bytes]]) -> tuple[bytes, str]:
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
        safe_filename = _quote_header_value(filename)
        parts.append(
            sep
            + f'Content-Disposition: form-data; name="files[{i}]"; filename="{safe_filename}"\r\n'.encode()
            + f"Content-Type: {content_type}\r\n\r\n".encode()
            + file_bytes
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def build_form_multipart_body(
    fields: Mapping[str, object], file_field_name: str, filename: str, file_bytes: bytes
) -> tuple[bytes, str]:
    """Encode a plain multipart/form-data body: simple string fields plus
    one named file part. Discord's usual attachment convention wraps
    everything in a payload_json part and numbered files[n] parts (see
    build_multipart_body above), but a handful of older, non-message
    endpoints (Create Guild Sticker's `file` field) just want ordinary form
    fields instead."""
    boundary = "cordless-" + uuid.uuid4().hex
    sep = f"--{boundary}\r\n".encode()

    parts: list[bytes] = []
    for name, value in fields.items():
        header = f'Content-Disposition: form-data; name="{_quote_header_value(name)}"\r\n\r\n'.encode()
        parts.append(sep + header + str(value).encode() + b"\r\n")

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    safe_field_name = _quote_header_value(file_field_name)
    safe_filename = _quote_header_value(filename)
    parts.append(
        sep
        + f'Content-Disposition: form-data; name="{safe_field_name}"; filename="{safe_filename}"\r\n'.encode()
        + f"Content-Type: {content_type}\r\n\r\n".encode()
        + file_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def parse_multipart_payload(body: bytes) -> Any:
    """Extract the JSON payload_json part back out of a multipart body built
    by build_multipart_body(): the inverse operation, used by
    cordless.testing to decode a file-attachment response."""
    marker = b'name="payload_json"'
    start = body.index(marker)
    json_start = body.index(b"\r\n\r\n", start) + 4
    json_end = body.index(b"\r\n--", json_start)
    return json.loads(body[json_start:json_end])
