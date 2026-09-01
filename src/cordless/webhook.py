# pyright: strict
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
from typing import Any

from ._multipart import build_multipart_body
from ._payload import _FLAG_UI_KIT, _attach_files, _contains_uikit
from ._useragent import USER_AGENT
from .errors import discord_http_error
from .ratelimit import retry_after_wait

_TIMEOUT = 10

# Backstop on total time spent sleeping across 429 retries, matching
# _rest/_client.py's _MAX_RETRY_SECONDS. A single retry_after is still
# honoured in full (retrying early just draws more 429s), but once that
# budget is spent the next attempt gives up rather than stacking another
# long sleep onto an invocation that is very likely already past its own
# Lambda timeout. A caller doing bursty webhook sends from the default 10s
# function should raise `timeout` in cordless.toml or move to defer_worker.
_MAX_RETRY_SECONDS = 30.0

# Same rationale, and same values, as _rest/_client.py's _IDEMPOTENT_METHODS:
# duplicated rather than imported for the same reason UNSET is below, since
# this module stays dependency-free from _rest/_client.py on purpose (see
# docstring). POST/PATCH aren't included, since Discord gives no guarantee
# that resending one is safe if the first attempt actually reached Discord
# and was processed before the connection dropped.
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})


class _Unset:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


# a local sentinel rather than importing _rest._client's, since this module
# stays dependency-free on purpose (see module docstring)
UNSET = _Unset()

_URL_RE = re.compile(r"discord(?:app)?\.com/api(?:/v\d+)?/webhooks/(\d+)/([\w-]+)")

# Kept open across invocations in a warm Lambda container, so most requests
# skip the TLS handshake instead of paying for it every time.
_conn: HTTPSConnection | None = None
_conn_lock = threading.Lock()


def _send(method: str, path: str, body: bytes | None, headers: dict[str, str]) -> tuple[int, bytes]:
    global _conn
    with _conn_lock:
        if _conn is None:
            _conn = HTTPSConnection("discord.com", timeout=_TIMEOUT)
        try:
            _conn.request(method, path, body, headers)
            resp = _conn.getresponse()
            return resp.status, resp.read()
        except (HTTPException, OSError):
            # the other end closed the kept-alive connection. Always drop it
            # and open a fresh one so the next call doesn't inherit a dead
            # socket, but only actually resend this request for idempotent
            # methods: if Discord already received and processed it before
            # the connection died, resending a POST/PATCH would duplicate
            # whatever it did (e.g. sending the same message twice)
            _conn.close()
            _conn = HTTPSConnection("discord.com", timeout=_TIMEOUT)
            if method not in _IDEMPOTENT_METHODS:
                raise
            _conn.request(method, path, body, headers)
            resp = _conn.getresponse()
            return resp.status, resp.read()


def parse_webhook_url(url: str) -> tuple[str, str]:
    """Extract (webhook_id, webhook_token) from a full Discord webhook URL."""
    match = _URL_RE.search(url)
    if not match:
        # url is typically a real webhook URL passed in specifically to
        # extract its token, so it must never be echoed back. A caller
        # passing in a subtly malformed one (trailing slash, wrong host
        # casing) would otherwise land its live token in whatever logs
        # this exception surfaces to (e.g. Lambda's default unhandled
        # exception logging, since this isn't a CordlessError app.py catches).
        raise ValueError("Not a Discord webhook URL: expected something matching discord.com/api/webhooks/<id>/<token>")
    return match.group(1), match.group(2)


def build_payload(
    content: Any,
    embeds: Any,
    components: Any,
    *,
    username: str | None = None,
    avatar_url: str | None = None,
    tts: bool = False,
    allowed_mentions: Any = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {}
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


def _request(method: str, path: str, body: bytes | None = None, content_type: str | None = None) -> tuple[int, bytes]:
    """Make a webhooks/{id}/{token}/... call, retrying on 429 (honouring retry_after).

    A webhook's id+token pair is its own credential and its own bucket, not
    shared with anything else, so a local retry is all that's needed here.
    """
    headers = {"User-Agent": USER_AGENT}
    if content_type is not None:
        headers["Content-Type"] = content_type

    deadline = time.monotonic() + _MAX_RETRY_SECONDS
    status, data = 0, b""
    for attempt in range(3):
        status, data = _send(method, path, body, headers)

        if status == 429 and attempt < 2:
            # already spent the retry budget on a previous wait? stop rather
            # than stacking another full retry_after sleep. Checked after the
            # sleep, not before, so a single large retry_after is still
            # honoured in full.
            if time.monotonic() >= deadline:
                break
            try:
                retry_after = float(json.loads(data).get("retry_after", 1))
            except (TypeError, ValueError, AttributeError):
                retry_after = 1.0
            time.sleep(retry_after_wait(retry_after))
            continue
        break

    if status >= 300:
        raise discord_http_error(status, data.decode(errors="replace"), body=data)
    return status, data


def _encode(payload: Any, files: Any) -> tuple[bytes, str]:
    if files:
        _attach_files(payload, files)
        return build_multipart_body(payload, files)
    return json.dumps(payload).encode(), "application/json"


def _wait_qs(wait: bool, thread_id: str | None) -> str:
    query: list[str] = []
    if wait:
        query.append("wait=true")
    if thread_id:
        query.append(f"thread_id={thread_id}")
    return ("?" + "&".join(query)) if query else ""


def execute(
    webhook_id: str,
    webhook_token: str,
    payload: Any,
    files: Any = None,
    wait: bool = False,
    thread_id: str | None = None,
) -> tuple[int, bytes]:
    """POST a message to a webhook. Returns (status, body)."""
    body, content_type = _encode(payload, files)
    path = f"/api/v10/webhooks/{webhook_id}/{webhook_token}{_wait_qs(wait, thread_id)}"
    return _request("POST", path, body, content_type)


def execute_slack_compatible(
    webhook_id: str, webhook_token: str, payload: Any, wait: bool = False, thread_id: str | None = None
) -> tuple[int, bytes]:
    """POST a Slack-formatted payload straight through to Discord."""
    body = json.dumps(payload).encode()
    path = f"/api/v10/webhooks/{webhook_id}/{webhook_token}/slack{_wait_qs(wait, thread_id)}"
    return _request("POST", path, body, "application/json")


def execute_github_compatible(
    webhook_id: str, webhook_token: str, payload: Any, wait: bool = False, thread_id: str | None = None
) -> tuple[int, bytes]:
    """POST a GitHub-formatted payload straight through to Discord."""
    body = json.dumps(payload).encode()
    path = f"/api/v10/webhooks/{webhook_id}/{webhook_token}/github{_wait_qs(wait, thread_id)}"
    return _request("POST", path, body, "application/json")


def get_webhook(webhook_id: str, webhook_token: str) -> tuple[int, bytes]:
    """GET the webhook itself, authenticated with its own token. The
    returned object omits `user`, unlike the bot-token equivalent."""
    return _request("GET", f"/api/v10/webhooks/{webhook_id}/{webhook_token}")


def edit_webhook(webhook_id: str, webhook_token: str, name: Any = UNSET, avatar: Any = UNSET) -> tuple[int, bytes]:
    """PATCH the webhook's own name/avatar, authenticated with its own
    token. Unlike the bot-token equivalent, this can't move it to a
    different channel_id. avatar can be cleared by passing None."""
    payload: dict[str, Any] = {}
    if name is not UNSET:
        payload["name"] = name
    if avatar is not UNSET:
        payload["avatar"] = avatar
    body = json.dumps(payload).encode()
    return _request("PATCH", f"/api/v10/webhooks/{webhook_id}/{webhook_token}", body, "application/json")


def get_message(webhook_id: str, webhook_token: str, message_id: str = "@original") -> tuple[int, bytes]:
    """GET a message previously sent through this webhook."""
    path = f"/api/v10/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}"
    return _request("GET", path)


def edit_message(
    webhook_id: str, webhook_token: str, message_id: str, payload: Any, files: Any = None
) -> tuple[int, bytes]:
    """PATCH a message previously sent through this webhook."""
    body, content_type = _encode(payload, files)
    path = f"/api/v10/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}"
    return _request("PATCH", path, body, content_type)


def delete_message(webhook_id: str, webhook_token: str, message_id: str) -> tuple[int, bytes]:
    """DELETE a message previously sent through this webhook."""
    path = f"/api/v10/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}"
    return _request("DELETE", path)


def delete_webhook(webhook_id: str, webhook_token: str) -> tuple[int, bytes]:
    """DELETE the webhook itself, authenticated with its own token (no bot token needed)."""
    return _request("DELETE", f"/api/v10/webhooks/{webhook_id}/{webhook_token}")
