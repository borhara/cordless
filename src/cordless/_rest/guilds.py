"""Guild management REST endpoints (Discord API v10).

Members and roles live in members.py, not here, despite technically sharing
the /guilds/{guild.id}/... path prefix - they are big enough resources on
their own to warrant a separate module and a separate rollout phase."""

from ..models import Guild
from . import _client
from ._client import UNSET
from .models import (
    Ban,
    BulkBanResult,
    GuildOnboarding,
    GuildWidget,
    GuildWidgetSettings,
    IncidentsData,
    Integration,
    Invite,
    VoiceRegion,
    WelcomeScreen,
)


async def fetch_guild(guild_id, *, with_counts=False, token=None):
    qs = _client.query_string(with_counts=with_counts)
    data = await _client.request("GET", f"/guilds/{guild_id}{qs}", token=token)
    return Guild(data)


async def fetch_guild_preview(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/preview", token=token)
    return Guild(data)


async def edit_guild(
    guild_id,
    *,
    name=UNSET,
    region=UNSET,
    verification_level=UNSET,
    default_message_notifications=UNSET,
    explicit_content_filter=UNSET,
    afk_channel_id=UNSET,
    afk_timeout=UNSET,
    icon=UNSET,
    splash=UNSET,
    discovery_splash=UNSET,
    banner=UNSET,
    system_channel_id=UNSET,
    system_channel_flags=UNSET,
    rules_channel_id=UNSET,
    public_updates_channel_id=UNSET,
    preferred_locale=UNSET,
    features=UNSET,
    description=UNSET,
    premium_progress_bar_enabled=UNSET,
    safety_alerts_channel_id=UNSET,
    reason=None,
    token=None,
):
    """Most nullable fields (afk_channel_id, icon, splash, ...) can be
    cleared by passing None."""
    payload = _client.payload(
        name=name,
        region=region,
        verification_level=verification_level,
        default_message_notifications=default_message_notifications,
        explicit_content_filter=explicit_content_filter,
        afk_channel_id=afk_channel_id,
        afk_timeout=afk_timeout,
        icon=icon,
        splash=splash,
        discovery_splash=discovery_splash,
        banner=banner,
        system_channel_id=system_channel_id,
        system_channel_flags=system_channel_flags,
        rules_channel_id=rules_channel_id,
        public_updates_channel_id=public_updates_channel_id,
        preferred_locale=preferred_locale,
        features=features,
        description=description,
        premium_progress_bar_enabled=premium_progress_bar_enabled,
        safety_alerts_channel_id=safety_alerts_channel_id,
    )
    data = await _client.request("PATCH", f"/guilds/{guild_id}", payload, token=token, reason=reason)
    return Guild(data)


async def fetch_guild_bans(guild_id, *, limit=None, before=None, after=None, token=None):
    qs = _client.query_string(limit=limit, before=before, after=after)
    data = await _client.request("GET", f"/guilds/{guild_id}/bans{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return [Ban(b) for b in data]


async def fetch_guild_ban(guild_id, user_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/bans/{user_id}", token=token)
    return Ban(data)


async def create_guild_ban(
    guild_id, user_id, *, delete_message_seconds=UNSET, delete_message_days=UNSET, reason=None, token=None
):
    payload = _client.payload(delete_message_seconds=delete_message_seconds, delete_message_days=delete_message_days)
    await _client.request("PUT", f"/guilds/{guild_id}/bans/{user_id}", payload, token=token, reason=reason)


async def remove_guild_ban(guild_id, user_id, *, reason=None, token=None):
    await _client.request("DELETE", f"/guilds/{guild_id}/bans/{user_id}", token=token, reason=reason)


async def bulk_guild_ban(guild_id, user_ids, *, delete_message_seconds=UNSET, reason=None, token=None):
    payload = _client.payload(user_ids=user_ids, delete_message_seconds=delete_message_seconds)
    data = await _client.request("POST", f"/guilds/{guild_id}/bulk-ban", payload, token=token, reason=reason)
    return BulkBanResult(data)


async def fetch_guild_prune_count(guild_id, *, days=None, include_roles=None, token=None):
    qs = _client.query_string(days=days, include_roles=",".join(include_roles) if include_roles else None)
    data = await _client.request("GET", f"/guilds/{guild_id}/prune{qs}", token=token)
    assert data is not None, "GET always returns a body"
    return data["pruned"]


async def begin_guild_prune(
    guild_id, *, days=UNSET, compute_prune_count=UNSET, include_roles=UNSET, reason=None, token=None
):
    payload = _client.payload(days=days, compute_prune_count=compute_prune_count, include_roles=include_roles)
    data = await _client.request("POST", f"/guilds/{guild_id}/prune", payload, token=token, reason=reason)
    assert data is not None, "POST always returns a body here"
    return data["pruned"]


async def fetch_guild_voice_regions(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/regions", token=token)
    assert data is not None, "GET always returns a body"
    return [VoiceRegion(r) for r in data]


async def fetch_guild_invites(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/invites", token=token)
    assert data is not None, "GET always returns a body"
    return [Invite(i) for i in data]


async def fetch_guild_integrations(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/integrations", token=token)
    assert data is not None, "GET always returns a body"
    return [Integration(i) for i in data]


async def delete_guild_integration(guild_id, integration_id, *, token=None):
    await _client.request("DELETE", f"/guilds/{guild_id}/integrations/{integration_id}", token=token)


async def fetch_guild_widget_settings(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/widget", token=token)
    return GuildWidgetSettings(data)


async def edit_guild_widget(guild_id, *, enabled=UNSET, channel_id=UNSET, token=None):
    payload = _client.payload(enabled=enabled, channel_id=channel_id)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/widget", payload, token=token)
    return GuildWidgetSettings(data)


async def fetch_guild_widget(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/widget.json", token=token)
    return GuildWidget(data)


async def fetch_guild_vanity_url(guild_id, *, token=None):
    """`code` is null on the returned partial invite if the guild has no
    vanity url set."""
    data = await _client.request("GET", f"/guilds/{guild_id}/vanity-url", token=token)
    return Invite(data)


async def fetch_guild_welcome_screen(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/welcome-screen", token=token)
    return WelcomeScreen(data)


async def edit_guild_welcome_screen(guild_id, *, enabled=UNSET, welcome_channels=UNSET, description=UNSET, token=None):
    payload = _client.payload(enabled=enabled, welcome_channels=welcome_channels, description=description)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/welcome-screen", payload, token=token)
    return WelcomeScreen(data)


async def fetch_guild_onboarding(guild_id, *, token=None):
    data = await _client.request("GET", f"/guilds/{guild_id}/onboarding", token=token)
    return GuildOnboarding(data)


async def edit_guild_onboarding(
    guild_id, *, prompts=UNSET, default_channel_ids=UNSET, enabled=UNSET, mode=UNSET, token=None
):
    payload = _client.payload(prompts=prompts, default_channel_ids=default_channel_ids, enabled=enabled, mode=mode)
    data = await _client.request("PUT", f"/guilds/{guild_id}/onboarding", payload, token=token)
    return GuildOnboarding(data)


async def edit_guild_incident_actions(guild_id, *, invites_disabled_until=UNSET, dms_disabled_until=UNSET, token=None):
    payload = _client.payload(invites_disabled_until=invites_disabled_until, dms_disabled_until=dms_disabled_until)
    data = await _client.request("PUT", f"/guilds/{guild_id}/incident-actions", payload, token=token)
    return IncidentsData(data)
