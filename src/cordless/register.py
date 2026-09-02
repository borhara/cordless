import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, cast

from ._useragent import USER_AGENT

API_BASE = "https://discord.com/api/v10"


def get_application_id(bot_token: str) -> Any:
    request = urllib.request.Request(
        f"{API_BASE}/oauth2/applications/@me",
        method="GET",
        headers={"Authorization": f"Bot {bot_token}", "User-Agent": USER_AGENT},
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())["id"]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Failed to resolve application id from bot token ({exc.code}): {exc.read().decode()}"
        ) from exc


def get_client_credentials_token(client_id: str, client_secret: str) -> Any:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode(
        {"grant_type": "client_credentials", "scope": "applications.commands.update"}
    ).encode()

    request = urllib.request.Request(
        f"{API_BASE}/oauth2/token",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())["access_token"]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Failed to obtain a client-credentials token ({exc.code}): {exc.read().decode()}") from exc


def sync_commands(
    commands: Any,
    guild_id: str | None = None,
    bot_token: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> Any:
    """Overwrite Discord's registered slash commands to match `commands`.

    Authenticate either with a bot token, or with a client id + secret via
    OAuth2's client credentials grant. The latter needs no bot user at all,
    which suits apps that only ever respond to HTTP interactions. If both are
    given, the bot token wins.

    The application id is resolved from the bot token (or is the client id
    directly), so global commands (the default, `guild_id=None`) are pushed
    to every guild that has authorized the app, for every user. Global
    commands can take up to an hour to propagate; pass `guild_id` during
    development for instant updates scoped to a single server.
    """
    if bot_token:
        application_id = get_application_id(bot_token)
        authorization = f"Bot {bot_token}"
    elif client_id and client_secret:
        application_id = client_id
        authorization = f"Bearer {get_client_credentials_token(client_id, client_secret)}"
    else:
        raise ValueError("Provide either bot_token, or both client_id and client_secret")

    if guild_id:
        url = f"{API_BASE}/applications/{application_id}/guilds/{guild_id}/commands"
    else:
        url = f"{API_BASE}/applications/{application_id}/commands"

    request = urllib.request.Request(
        url,
        data=json.dumps(commands).encode(),
        method="PUT",
        headers={
            "Authorization": authorization,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        raise RuntimeError(
            f"Failed to register commands ({exc.code}): {_explain_form_errors(body, commands) or body}"
        ) from exc


def _explain_form_errors(body: str, commands: Any) -> str | None:
    """Rewrite Discord's positional Invalid Form Body errors (`errors.0.
    options.18.description`) into lines that name the command and option at
    fault. Returns None when the body is not that shape."""
    try:
        errors = json.loads(body).get("errors")
    except (ValueError, AttributeError):
        return None
    if not isinstance(errors, dict):
        return None

    lines: list[str] = []

    def walk(node: Any, defn: Any, trail: list[str]) -> None:
        if not isinstance(node, dict):
            return
        node = cast("dict[str, Any]", node)
        leaf = node.get("_errors")
        if isinstance(leaf, list) and leaf:
            message = "; ".join(item.get("message", "") for item in cast("list[Any]", leaf))
            lines.append(f"{', '.join(trail)}: {message}" if trail else message)
            return
        for key, child in node.items():
            if key == "_errors":
                continue
            if key.isdigit() and isinstance(defn, list):
                items = cast("list[Any]", defn)
                index = int(key)
                item = items[index] if index < len(items) else None
                if not isinstance(item, dict) or "name" not in item:
                    walk(child, item, trail + [f"[{key}]"])
                elif not trail:
                    walk(child, item, [f"command {cast('dict[str, Any]', item)['name']!r}"])
                else:
                    item_d = cast("dict[str, Any]", item)
                    labels: dict[object, str] = {1: "subcommand", 2: "group"}
                    label = labels.get(item_d.get("type"), "option")
                    walk(child, item, trail + [f"{label} {item_d['name']!r}"])
            elif key in ("options", "choices") and isinstance(defn, dict):
                walk(child, cast("dict[str, Any]", defn).get(key), trail)
            else:
                walk(child, cast("dict[str, Any]", defn).get(key) if isinstance(defn, dict) else None, trail + [key])

    walk(errors, commands, [])
    return "; ".join(lines) or None
