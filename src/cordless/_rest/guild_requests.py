"""Guild join request REST endpoints (Discord API v10).

Membership screening's approve/reject workflow, for guilds that require an
application form before letting someone in.
"""

from . import _client
from .models import GuildJoinRequest


async def fetch_guild_join_requests(guild_id, *, status=None, before=None, after=None, limit=None, token=None):
    qs = _client.query_string(status=status, before=before, after=after, limit=limit)
    data = await _client.request("GET", f"/guilds/{guild_id}/requests{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [GuildJoinRequest(r) for r in data.get("guild_join_requests", [])]


async def edit_guild_join_request(guild_id, request_id, action, *, rejection_reason=None, token=None):
    """action is "APPROVED" or "REJECTED". rejection_reason is only used
    when rejecting."""
    payload = {"action": action}
    if rejection_reason is not None:
        payload["rejection_reason"] = rejection_reason
    data = await _client.request("PATCH", f"/guilds/{guild_id}/requests/{request_id}", payload, token=token)
    return GuildJoinRequest(data)
