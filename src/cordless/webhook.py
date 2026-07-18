"""Discord webhook execution: send/edit/delete messages via a webhook id+token.

Unlike send_message/edit_message in app.py, none of this needs DISCORD_BOT_TOKEN -
a webhook's id+token pair is its own credential. Kept dependency-free (stdlib
HTTPSConnection, like defer.py) so it stays cheap to import on the direct
response path.
"""

import json
import re
import threading
import time
from http.client import HTTPException, HTTPSConnection

from ._multipart import build_multipart_body
from .context import _FLAG_UI_KIT, _attach_files, _contains_uikit

_TIMEOUT = 10

_URL_RE = re.compile(r"discord(?:app)?\.com/api(?:/v\d+)?/webhooks/(\d+)/([\w-]+)")

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


def parse_webhook_url(url):
    """Extract (webhook_id, webhook_token) from a full Discord webhook URL."""
    match = _URL_RE.search(url)
    if not match:
        raise ValueError(f"Not a Discord webhook URL: {url!r}")
    return match.group(1), match.group(2)


def build_payload(content, embeds, components, *, username=None, avatar_url=None, tts=False, allowed_mentions=None):
    data = {}
    if content is not None:
        data["content"] = content
    if embeds is not None:
        data["embeds"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in embeds]
    if components is not None:
        data["components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in components]
    if username is not None:
        data["username"] = username
    if avatar_url is not None:
        data["avatar_url"] = avatar_url
    if tts:
        data["tts"] = True
    if allowed_mentions is not None:
        data["allowed_mentions"] = allowed_mentions

    if _contains_uikit(components):
        data["flags"] = _FLAG_UI_KIT
    return data


def _request(method, path, body=None, content_type=None):
    """Make a webhooks/{id}/{token}/... call, retrying on 429 (honouring retry_after).

    A webhook's id+token pair is its own credential and its own bucket, not
    shared with anything else, so a local retry is all that's needed here.
    """
    headers = {"User-Agent": "cordless"}
    if content_type is not None:
        headers["Content-Type"] = content_type

    status, data = 0, b""
    for attempt in range(3):
        status, data = _send(method, path, body, headers)

        if status == 429 and attempt < 2:
            try:
                retry_after = float(json.loads(data).get("retry_after", 1))
            except (ValueError, AttributeError):
                retry_after = 1.0
            time.sleep(min(retry_after, 5))
            continue
        break

    if status >= 300:
        raise RuntimeError(f"Discord API error {status}: {data.decode(errors='replace')}")
    return status, data


def _encode(payload, files):
    if files:
        _attach_files(payload, files)
        return build_multipart_body(payload, files)
    return json.dumps(payload).encode(), "application/json"


def execute(webhook_id, webhook_token, payload, files=None, wait=False, thread_id=None):
    """POST a message to a webhook. Returns (status, body)."""
    query = []
    if wait:
        query.append("wait=true")
    if thread_id:
        query.append(f"thread_id={thread_id}")
    qs = ("?" + "&".join(query)) if query else ""
    body, content_type = _encode(payload, files)
    return _request("POST", f"/api/v10/webhooks/{webhook_id}/{webhook_token}{qs}", body, content_type)


def edit_message(webhook_id, webhook_token, message_id, payload, files=None):
    """PATCH a message previously sent through this webhook."""
    body, content_type = _encode(payload, files)
    path = f"/api/v10/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}"
    return _request("PATCH", path, body, content_type)


def delete_message(webhook_id, webhook_token, message_id):
    """DELETE a message previously sent through this webhook."""
    path = f"/api/v10/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}"
    return _request("DELETE", path)


def delete_webhook(webhook_id, webhook_token):
    """DELETE the webhook itself, authenticated with its own token (no bot token needed)."""
    return _request("DELETE", f"/api/v10/webhooks/{webhook_id}/{webhook_token}")
