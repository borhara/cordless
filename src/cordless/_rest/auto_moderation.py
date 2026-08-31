"""Auto moderation REST endpoints (Discord API v10)."""

from . import _client
from ._client import UNSET
from .models import AutoModerationRule


async def fetch_auto_moderation_rules(guild_id, *, token=None):
    """Fetches every auto moderation rule configured for the guild."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/auto-moderation/rules", token=token)
    return [AutoModerationRule(r) for r in data]


async def fetch_auto_moderation_rule(guild_id, rule_id, *, token=None):
    """Fetches a single auto moderation rule by id."""
    data = await _client.request("GET", f"/guilds/{guild_id}/auto-moderation/rules/{rule_id}", token=token)
    return AutoModerationRule(data)


async def create_auto_moderation_rule(
    guild_id,
    name,
    event_type,
    trigger_type,
    actions,
    *,
    trigger_metadata=UNSET,
    enabled=UNSET,
    exempt_roles=UNSET,
    exempt_channels=UNSET,
    token=None,
):
    """Creates a new auto moderation rule. trigger_metadata's shape
    depends on trigger_type, a keyword filter needs keyword_filter,
    a mention spam rule needs mention_total_limit, and so on."""
    payload = _client.payload(
        name=name,
        event_type=event_type,
        trigger_type=trigger_type,
        trigger_metadata=trigger_metadata,
        actions=actions,
        enabled=enabled,
        exempt_roles=exempt_roles,
        exempt_channels=exempt_channels,
    )
    data = await _client.request("POST", f"/guilds/{guild_id}/auto-moderation/rules", payload, token=token)
    return AutoModerationRule(data)


async def edit_auto_moderation_rule(
    guild_id,
    rule_id,
    *,
    name=UNSET,
    event_type=UNSET,
    trigger_metadata=UNSET,
    actions=UNSET,
    enabled=UNSET,
    exempt_roles=UNSET,
    exempt_channels=UNSET,
    token=None,
):
    """Edits an existing auto moderation rule. Only the fields passed are
    changed, everything else keeps its current value."""
    payload = _client.payload(
        name=name,
        event_type=event_type,
        trigger_metadata=trigger_metadata,
        actions=actions,
        enabled=enabled,
        exempt_roles=exempt_roles,
        exempt_channels=exempt_channels,
    )
    data = await _client.request("PATCH", f"/guilds/{guild_id}/auto-moderation/rules/{rule_id}", payload, token=token)
    return AutoModerationRule(data)


async def delete_auto_moderation_rule(guild_id, rule_id, *, token=None):
    """Deletes an auto moderation rule."""
    await _client.request("DELETE", f"/guilds/{guild_id}/auto-moderation/rules/{rule_id}", token=token)
