import base64
import json
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://discord.com/api/v10"

# Discord's API sits behind Cloudflare, which blocks urllib's default
# "Python-urllib/x.y" User-Agent outright (403, error code 1010) regardless
# of whether the credentials are valid. Any descriptive User-Agent avoids it.
USER_AGENT = "cordless (https://github.com/borhara/cordless)"


def _get_application_id(bot_token):
    request = urllib.request.Request(
        f"{API_BASE}/oauth2/applications/@me",
        method="GET",
        headers={"Authorization": f"Bot {bot_token}", "User-Agent": USER_AGENT},
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())["id"]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Failed to resolve application id from bot token ({exc.code}): {exc.read().decode()}") from exc


def _get_client_credentials_token(client_id, client_secret):
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


def sync_commands(commands, guild_id=None, bot_token=None, client_id=None, client_secret=None):
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
        application_id = _get_application_id(bot_token)
        authorization = f"Bot {bot_token}"
    elif client_id and client_secret:
        application_id = client_id
        authorization = f"Bearer {_get_client_credentials_token(client_id, client_secret)}"
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
        raise RuntimeError(f"Failed to register commands ({exc.code}): {exc.read().decode()}") from exc
