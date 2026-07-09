"""Discord webhook execution: send/edit/delete messages via a webhook id+token.

Unlike send_message/edit_message in app.py, none of this needs DISCORD_BOT_TOKEN -
a webhook's id+token pair is its own credential. Kept dependency-free (stdlib
HTTPSConnection, like defer.py) so it stays cheap to import on the direct
response path.
"""

import json
import re
from http.client import HTTPSConnection

from ._multipart import build_multipart_body
from .context import _FLAG_UI_KIT, _contains_uikit

_TIMEOUT = 10

_URL_RE = re.compile(r"discord(?:app)?\.com/api(?:/v\d+)?/webhooks/(\d+)/([\w-]+)")


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
    conn = HTTPSConnection("discord.com", timeout=_TIMEOUT)
    try:
        headers = {"User-Agent": "cordless"}
        if content_type is not None:
            headers["Content-Type"] = content_type
        conn.request(method, path, body, headers)
        resp = conn.getresponse()
        status = resp.status
        data = resp.read()
    finally:
        conn.close()
    if status >= 300:
        print(f"[cordless] webhook {method} {path} {status}: {data.decode(errors='replace')}")
    return status, data


def _encode(payload, files):
    if files:
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
