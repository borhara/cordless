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
