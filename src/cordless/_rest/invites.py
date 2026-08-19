"""Standalone Invite REST endpoints (Discord API v10).

Fetching/creating invites scoped to a particular channel or guild live in
channels.py and guilds.py instead (they're documented there in Discord's own
API reference too) - this module only covers the two endpoints keyed by
invite code alone.

Not covered: Get/Update Target Users and Get Target Users Job Status. Those
manage a CSV allowlist of users for an invite, a fairly niche feature with a
file-upload/download shape unlike everything else in this module, left out
for now rather than half-supported.
"""

from . import _client
from .models import Invite


async def fetch_invite(code, *, with_counts=None, guild_scheduled_event_id=None, token=None):
    params = [
        p
        for p in (
            "with_counts=true" if with_counts else None,
            f"guild_scheduled_event_id={guild_scheduled_event_id}" if guild_scheduled_event_id else None,
        )
        if p
    ]
    qs = ("?" + "&".join(params)) if params else ""
    data = await _client.request("GET", f"/invites/{code}{qs}", token=token)
    return Invite(data)


async def delete_invite(code, *, token=None):
    data = await _client.request("DELETE", f"/invites/{code}", token=token)
    return Invite(data)
