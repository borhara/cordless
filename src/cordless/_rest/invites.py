"""Invite endpoints keyed by code alone (Discord API v10). Channel- and
guild-scoped invite listing and creation are in channels.py and guilds.py.

The target-users endpoints manage a CSV allowlist restricting who can use an
invite; they send and return raw CSV rather than JSON.
"""

from .._multipart import build_form_multipart_body
from . import _client
from .models import Invite, TargetUsersJobStatus


async def fetch_invite(
    code: str, *, with_counts: bool | None = None, guild_scheduled_event_id: str | None = None, token: str | None = None
) -> Invite:
    """Fetches an invite by its code. with_counts adds approximate member
    and presence counts; guild_scheduled_event_id attaches a scheduled
    event to the returned invite so a client can offer to add it to the
    joiner's calendar."""
    params: list[str] = [
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


async def delete_invite(code: str, *, token: str | None = None) -> Invite:
    """Requires MANAGE_CHANNELS on the channel, or MANAGE_GUILD. Returns the deleted `Invite`."""
    data = await _client.request("DELETE", f"/invites/{code}", token=token)
    return Invite(data)


async def fetch_invite_target_users(code: str, *, token: str | None = None) -> str:
    """Returns the raw CSV body Discord sends back, not a parsed list -
    there's no documented column schema to parse it against."""
    data = await _client.request_raw("GET", f"/invites/{code}/target-users", token=token)
    return data.decode()


async def edit_invite_target_users(code: str, filename: str, file_bytes: bytes, *, token: str | None = None) -> None:
    """Replaces the invite's whole target user allowlist with the users
    listed in the given CSV file."""
    raw_body = build_form_multipart_body({}, "target_users_file", filename, file_bytes)
    await _client.request("PUT", f"/invites/{code}/target-users", raw_body=raw_body, token=token)


async def fetch_invite_target_users_job_status(code: str, *, token: str | None = None) -> TargetUsersJobStatus:
    """Fetches the processing status of the CSV uploaded through
    edit_invite_target_users."""
    data = await _client.request("GET", f"/invites/{code}/target-users/job-status", token=token)
    return TargetUsersJobStatus(data)
