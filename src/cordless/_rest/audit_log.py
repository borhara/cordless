"""Audit log REST endpoints (Discord API v10)."""

from . import _client
from .models import AuditLog


async def fetch_audit_log(guild_id, *, user_id=None, action_type=None, before=None, after=None, limit=None, token=None):
    params = [
        p
        for p in (
            f"user_id={user_id}" if user_id else None,
            f"action_type={action_type}" if action_type is not None else None,
            f"before={before}" if before else None,
            f"after={after}" if after else None,
            f"limit={limit}" if limit else None,
        )
        if p
    ]
    qs = ("?" + "&".join(params)) if params else ""
    data = await _client.request("GET", f"/guilds/{guild_id}/audit-logs{qs}", token=token)
    return AuditLog(data)
