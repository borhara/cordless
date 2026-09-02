"""Guild management REST endpoints (Discord API v10).

Members and roles are in members.py. Create Guild, Delete Guild and Modify
MFA Level are omitted: all three need guild ownership, which a bot can't have.
"""

from typing import Any

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


async def fetch_guild(guild_id: str, *, with_counts: bool = False, token: str | None = None) -> Guild:
    """Fetches a guild by id. with_counts adds approximate_member_count
    and approximate_presence_count to the result."""
    qs = _client.query_string(with_counts=with_counts)
    data = await _client.request("GET", f"/guilds/{guild_id}{qs}", token=token)
    return Guild(data)


async def fetch_guild_preview(guild_id: str, *, token: str | None = None) -> Guild:
    """Fetches a guild's public preview. Works even for guilds the bot
    isn't in, as long as the guild is discoverable or has its widget
    enabled."""
    data = await _client.request("GET", f"/guilds/{guild_id}/preview", token=token)
    return Guild(data)


async def edit_guild(
    guild_id: str,
    *,
    name: Any = UNSET,
    region: Any = UNSET,
    verification_level: Any = UNSET,
    default_message_notifications: Any = UNSET,
    explicit_content_filter: Any = UNSET,
    afk_channel_id: Any = UNSET,
    afk_timeout: Any = UNSET,
    icon: Any = UNSET,
    splash: Any = UNSET,
    discovery_splash: Any = UNSET,
    banner: Any = UNSET,
    system_channel_id: Any = UNSET,
    system_channel_flags: Any = UNSET,
    rules_channel_id: Any = UNSET,
    public_updates_channel_id: Any = UNSET,
    preferred_locale: Any = UNSET,
    features: Any = UNSET,
    description: Any = UNSET,
    premium_progress_bar_enabled: Any = UNSET,
    safety_alerts_channel_id: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> Guild:
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


async def fetch_guild_bans(
    guild_id: str,
    *,
    limit: int | None = None,
    before: str | None = None,
    after: str | None = None,
    token: str | None = None,
) -> list[Ban]:
    """A page of `Ban` objects. Requires BAN_MEMBERS."""
    qs = _client.query_string(limit=limit, before=before, after=after)
    data = await _client.request_json("GET", f"/guilds/{guild_id}/bans{qs}", token=token)
    return [Ban(b) for b in data]


async def fetch_guild_ban(guild_id: str, user_id: str, *, token: str | None = None) -> Ban:
    """Fetches a single ban by user id, or raises NotFound if the user
    isn't banned."""
    data = await _client.request("GET", f"/guilds/{guild_id}/bans/{user_id}", token=token)
    return Ban(data)


async def create_guild_ban(
    guild_id: str,
    user_id: str,
    *,
    delete_message_seconds: Any = UNSET,
    delete_message_days: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> None:
    """Bans a user, whether or not they're currently a member of the
    guild. delete_message_seconds (0 to 604800) also deletes that user's
    recent messages; delete_message_days is the older, day-granularity
    equivalent, kept for callers that still use it."""
    payload = _client.payload(delete_message_seconds=delete_message_seconds, delete_message_days=delete_message_days)
    await _client.request("PUT", f"/guilds/{guild_id}/bans/{user_id}", payload, token=token, reason=reason)


async def remove_guild_ban(guild_id: str, user_id: str, *, reason: str | None = None, token: str | None = None) -> None:
    """Requires BAN_MEMBERS."""
    await _client.request("DELETE", f"/guilds/{guild_id}/bans/{user_id}", token=token, reason=reason)


async def bulk_guild_ban(
    guild_id: str,
    user_ids: Any,
    *,
    delete_message_seconds: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> BulkBanResult:
    """Bans up to 200 users in one call. The result lists which ids were
    banned successfully and which failed, a partial failure doesn't raise
    on its own."""
    payload = _client.payload(user_ids=user_ids, delete_message_seconds=delete_message_seconds)
    data = await _client.request("POST", f"/guilds/{guild_id}/bulk-ban", payload, token=token, reason=reason)
    return BulkBanResult(data)


async def fetch_guild_prune_count(
    guild_id: str, *, days: int | None = None, include_roles: list[str] | None = None, token: str | None = None
) -> Any:
    """Counts how many members would be removed by a prune, without
    actually removing them. Members with a role in include_roles are
    counted even though they'd normally be exempt."""
    qs = _client.query_string(days=days, include_roles=",".join(include_roles) if include_roles else None)
    data = await _client.request_json("GET", f"/guilds/{guild_id}/prune{qs}", token=token)
    return data["pruned"]


async def begin_guild_prune(
    guild_id: str,
    *,
    days: Any = UNSET,
    compute_prune_count: Any = UNSET,
    include_roles: Any = UNSET,
    reason: str | None = None,
    token: str | None = None,
) -> Any:
    """Kicks every member who hasn't been seen for days and holds none of
    the guild's roles, unless their role is listed in include_roles. Set
    compute_prune_count=False on a large guild to skip counting the
    removed members and speed up the request."""
    payload = _client.payload(days=days, compute_prune_count=compute_prune_count, include_roles=include_roles)
    data = await _client.request_json("POST", f"/guilds/{guild_id}/prune", payload, token=token, reason=reason)
    return data["pruned"]


async def fetch_guild_voice_regions(guild_id: str, *, token: str | None = None) -> list[VoiceRegion]:
    """Fetches the voice regions available to this guild, ordered by how
    close they are to it (VIP regions first if the guild has them)."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/regions", token=token)
    return [VoiceRegion(r) for r in data]


async def fetch_guild_invites(guild_id: str, *, token: str | None = None) -> list[Invite]:
    """Fetches every invite for the guild, across all its channels, each
    with its own use count."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/invites", token=token)
    return [Invite(i) for i in data]


async def fetch_guild_integrations(guild_id: str, *, token: str | None = None) -> list[Integration]:
    """Fetches the guild's third-party integrations, Twitch, YouTube and
    the like."""
    data = await _client.request_json("GET", f"/guilds/{guild_id}/integrations", token=token)
    return [Integration(i) for i in data]


async def delete_guild_integration(guild_id: str, integration_id: str, *, token: str | None = None) -> None:
    """Removes an integration and deletes any webhooks or roles it
    created."""
    await _client.request("DELETE", f"/guilds/{guild_id}/integrations/{integration_id}", token=token)


async def fetch_guild_widget_settings(guild_id: str, *, token: str | None = None) -> GuildWidgetSettings:
    """Fetches whether the guild's server widget is enabled and which
    channel its invite points at."""
    data = await _client.request("GET", f"/guilds/{guild_id}/widget", token=token)
    return GuildWidgetSettings(data)


async def edit_guild_widget(
    guild_id: str, *, enabled: Any = UNSET, channel_id: Any = UNSET, token: str | None = None
) -> GuildWidgetSettings:
    """Turns the server widget on or off, or changes which channel its
    invite points at."""
    payload = _client.payload(enabled=enabled, channel_id=channel_id)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/widget", payload, token=token)
    return GuildWidgetSettings(data)


async def fetch_guild_widget(guild_id: str, *, token: str | None = None) -> GuildWidget:
    """Fetches the guild's public widget, an embeddable member list and
    invite link. Works with no authentication needed on Discord's side,
    but raises NotFound if the widget isn't enabled."""
    data = await _client.request("GET", f"/guilds/{guild_id}/widget.json", token=token)
    return GuildWidget(data)


async def fetch_guild_vanity_url(guild_id: str, *, token: str | None = None) -> Invite:
    """`code` is null on the returned partial invite if the guild has no
    vanity url set."""
    data = await _client.request("GET", f"/guilds/{guild_id}/vanity-url", token=token)
    return Invite(data)


async def fetch_guild_welcome_screen(guild_id: str, *, token: str | None = None) -> WelcomeScreen:
    """Fetches the guild's welcome screen, the recommended-channels prompt
    shown to new members."""
    data = await _client.request("GET", f"/guilds/{guild_id}/welcome-screen", token=token)
    return WelcomeScreen(data)


async def edit_guild_welcome_screen(
    guild_id: str,
    *,
    enabled: Any = UNSET,
    welcome_channels: Any = UNSET,
    description: Any = UNSET,
    token: str | None = None,
) -> WelcomeScreen:
    """Edits the guild's welcome screen. welcome_channels replaces the
    whole list of recommended channels, up to 5."""
    payload = _client.payload(enabled=enabled, welcome_channels=welcome_channels, description=description)
    data = await _client.request("PATCH", f"/guilds/{guild_id}/welcome-screen", payload, token=token)
    return WelcomeScreen(data)


async def fetch_guild_onboarding(guild_id: str, *, token: str | None = None) -> GuildOnboarding:
    """Fetches the guild's onboarding configuration, the prompts shown to
    new members to pick roles and channels."""
    data = await _client.request("GET", f"/guilds/{guild_id}/onboarding", token=token)
    return GuildOnboarding(data)


async def edit_guild_onboarding(
    guild_id: str,
    *,
    prompts: Any = UNSET,
    default_channel_ids: Any = UNSET,
    enabled: Any = UNSET,
    mode: Any = UNSET,
    token: str | None = None,
) -> GuildOnboarding:
    """Edits the guild's onboarding configuration. prompts replaces the
    whole set; enabling onboarding requires the guild to already meet
    Discord's rules channel and community setup requirements."""
    payload = _client.payload(prompts=prompts, default_channel_ids=default_channel_ids, enabled=enabled, mode=mode)
    data = await _client.request("PUT", f"/guilds/{guild_id}/onboarding", payload, token=token)
    return GuildOnboarding(data)


async def edit_guild_incident_actions(
    guild_id: str, *, invites_disabled_until: Any = UNSET, dms_disabled_until: Any = UNSET, token: str | None = None
) -> IncidentsData:
    """Sets or clears the guild's raid protection measures, temporarily
    pausing invites or DMs between members until the given timestamps.
    Pass None to clear a measure immediately."""
    payload = _client.payload(invites_disabled_until=invites_disabled_until, dms_disabled_until=dms_disabled_until)
    data = await _client.request("PUT", f"/guilds/{guild_id}/incident-actions", payload, token=token)
    return IncidentsData(data)
