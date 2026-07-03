import json
import urllib.error
import urllib.request

API_BASE = "https://discord.com/api/v10"


def sync_commands(application_id, bot_token, commands, guild_id=None):
    """Overwrite Discord's registered slash commands to match `commands`.

    Global commands can take up to an hour to propagate; pass `guild_id`
    during development for instant updates scoped to a single server.
    """
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
