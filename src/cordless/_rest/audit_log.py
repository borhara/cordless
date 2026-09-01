# pyright: strict
"""Audit log REST endpoints (Discord API v10)."""

from . import _client
from .models import AuditLog


async def fetch_audit_log(
    guild_id: str,
    *,
    user_id: str | None = None,
    action_type: int | None = None,
    before: str | None = None,
    after: str | None = None,
    limit: int | None = None,
    token: str | None = None,
) -> AuditLog:
    """Requires VIEW_AUDIT_LOG. before/after paginate by audit log entry id,
    not by any resource id."""
    qs = _client.query_string(user_id=user_id, action_type=action_type, before=before, after=after, limit=limit)
    data = await _client.request("GET", f"/guilds/{guild_id}/audit-logs{qs}", token=token)
    return AuditLog(data)
