"""Audit log REST endpoints (Discord API v10)."""

from . import _client
from .models import AuditLog


async def fetch_audit_log(guild_id, *, user_id=None, action_type=None, before=None, after=None, limit=None, token=None):
    """Requires VIEW_AUDIT_LOG. before/after paginate by audit log entry id,
    not by any resource id."""
    qs = _client.query_string(user_id=user_id, action_type=action_type, before=before, after=after, limit=limit)
    data = await _client.request("GET", f"/guilds/{guild_id}/audit-logs{qs}", token=token)
    return AuditLog(data)
