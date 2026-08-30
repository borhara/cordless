"""Standalone Invite REST endpoints (Discord API v10).

Fetching/creating invites scoped to a particular channel or guild live in
channels.py and guilds.py instead (they're documented there in Discord's own
API reference too) - this module only covers the endpoints keyed by invite
code alone.

Target users (fetch_invite_target_users/edit_invite_target_users/
fetch_invite_target_users_job_status) manage a CSV allowlist of users an
invite is restricted to - a fairly niche feature, and the only one here that
trades Discord's usual JSON body for a raw CSV upload/download.
"""

from .._multipart import build_form_multipart_body
from . import _client
from .models import Invite, TargetUsersJobStatus


async def fetch_invite(code, *, with_counts=None, guild_scheduled_event_id=None, token=None):
    """Fetches an invite by its code. with_counts adds approximate member
    and presence counts; guild_scheduled_event_id attaches a scheduled
    event to the returned invite so a client can offer to add it to the
    joiner's calendar."""
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
    """Deletes an invite, revoking it immediately."""
    data = await _client.request("DELETE", f"/invites/{code}", token=token)
    return Invite(data)


async def fetch_invite_target_users(code, *, token=None):
    """Returns the raw CSV body Discord sends back, not a parsed list -
    there's no documented column schema to parse it against."""
    data = await _client.request_raw("GET", f"/invites/{code}/target-users", token=token)
    return data.decode()


async def edit_invite_target_users(code, filename, file_bytes, *, token=None):
    """Replaces the invite's whole target user allowlist with the users
    listed in the given CSV file."""
    raw_body = build_form_multipart_body({}, "target_users_file", filename, file_bytes)
    await _client.request("PUT", f"/invites/{code}/target-users", raw_body=raw_body, token=token)


async def fetch_invite_target_users_job_status(code, *, token=None):
    """Fetches the processing status of the CSV uploaded through
    edit_invite_target_users."""
    data = await _client.request("GET", f"/invites/{code}/target-users/job-status", token=token)
    return TargetUsersJobStatus(data)
