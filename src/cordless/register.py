import json
import urllib.error
import urllib.request

API_BASE = "https://discord.com/api/v10"


def _get_application_id(bot_token):
    request = urllib.request.Request(
        f"{API_BASE}/oauth2/applications/@me",
        method="GET",
        headers={"Authorization": f"Bot {bot_token}"},
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())["id"]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Failed to resolve application id from bot token ({exc.code}): {exc.read().decode()}") from exc


def sync_commands(bot_token, commands, guild_id=None):
    """Overwrite Discord's registered slash commands to match `commands`.

    The application id is resolved from the bot token, so global commands
    (the default, `guild_id=None`) are pushed to every guild that has
    authorized the bot, for every user. Global commands can take up to an
    hour to propagate; pass `guild_id` during development for instant
    updates scoped to a single server.
    """
    application_id = _get_application_id(bot_token)

    if guild_id:
        url = f"{API_BASE}/applications/{application_id}/guilds/{guild_id}/commands"
    else:
        url = f"{API_BASE}/applications/{application_id}/commands"

    request = urllib.request.Request(
        url,
        data=json.dumps(commands).encode(),
        method="PUT",
        headers={
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Failed to register commands ({exc.code}): {exc.read().decode()}") from exc
