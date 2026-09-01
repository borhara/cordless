# pyright: strict
"""Shared dataclasses for REST responses.

Carry read-only convenience properties plus thin action methods (e.g.
thread.join()), but never a back-reference to a Cordless instance. Each
action method is a straight delegation to the same _rest/<resource>.py
function bot.<verb>_<resource>() already calls, using only this object's own
id and, optionally, an explicit token kwarg - both call shapes hit the exact
same code path, so there is no request logic duplicated between them.
"""

import asyncio
import json
from typing import Any

from .._base import DiscordObject


class ThreadMember(DiscordObject):
    """One entry from `thread.fetch_members()`/`thread.fetch_member()`.
    `.id`, `.user_id`, `.join_timestamp`, `.flags`, and any other field
    Discord sends."""


class Thread(DiscordObject):
    """A Discord thread, from `channel.start_thread_from_message()` and
    friends. `.id`, `.guild_id`, `.parent_id`, `.owner_id`, `.name`,
    `.type`, `.message_count`, `.member_count`, `.thread_metadata`,
    `.rate_limit_per_user`, and any other field Discord sends."""

    @property
    def archived(self) -> Any:
        return self._data.get("thread_metadata", {}).get("archived", False)

    @property
    def locked(self) -> Any:
        return self._data.get("thread_metadata", {}).get("locked", False)

    @property
    def mention(self) -> Any:
        return f"<#{self._data['id']}>"

    async def join(self, *, token: str | None = None) -> Any:
        """No-op if the bot is already a member."""
        await threads.join_thread(self.id, token=token)

    async def leave(self, *, token: str | None = None) -> Any:
        """The bot stops receiving the thread's messages."""
        await threads.leave_thread(self.id, token=token)

    async def add_member(self, user_id: str, *, token: str | None = None) -> Any:
        """Needs the bot in the thread; a private thread also needs SEND_MESSAGES_IN_THREADS."""
        await threads.add_thread_member(self.id, user_id, token=token)

    async def remove_member(self, user_id: str, *, token: str | None = None) -> Any:
        """Requires MANAGE_THREADS, or thread ownership for a private thread."""
        await threads.remove_thread_member(self.id, user_id, token=token)

    async def fetch_member(self, user_id: str, *, with_member: bool = False, token: str | None = None) -> Any:
        """Fetch a single member of this thread, as a `ThreadMember`."""
        return await threads.fetch_thread_member(self.id, user_id, with_member=with_member, token=token)

    async def fetch_members(
        self, *, with_member: bool = False, after: str | None = None, limit: int | None = None, token: str | None = None
    ) -> Any:
        """List this thread's members, as a list of `ThreadMember`."""
        return await threads.fetch_thread_members(
            self.id, with_member=with_member, after=after, limit=limit, token=token
        )


class Invite(DiscordObject):
    """A Discord invite, e.g. from `channel.fetch_invites()` or
    `channel.create_invite()`. `.code`, `.guild`, `.channel`, `.inviter`,
    `.uses`, `.max_uses`, `.max_age`, `.temporary`, and any other field
    Discord sends are available as attributes."""

    @property
    def url(self) -> Any:
        """Full `https://discord.gg/<code>` invite link."""
        return f"https://discord.gg/{self._data['code']}"

    async def fetch(self, **kwargs: Any) -> Any:
        """Re-fetch this invite by code. Returns the refreshed `Invite`."""
        return await invites.fetch_invite(self.code, **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Delete this invite. Returns the now-deleted `Invite`. Requires `MANAGE_CHANNELS` (or `MANAGE_GUILD` to
        remove any invite in the guild)."""
        return await invites.delete_invite(self.code, **kwargs)

    async def fetch_target_users(self, **kwargs: Any) -> Any:
        """Fetch this invite's target user allowlist, as raw CSV text."""
        return await invites.fetch_invite_target_users(self.code, **kwargs)

    async def edit_target_users(self, filename: str, file_bytes: bytes, **kwargs: Any) -> Any:
        """Replace this invite's target user allowlist from a CSV file."""
        await invites.edit_invite_target_users(self.code, filename, file_bytes, **kwargs)

    async def fetch_target_users_job_status(self, **kwargs: Any) -> Any:
        """Check the progress of a target user allowlist upload, as a
        `TargetUsersJobStatus`."""
        return await invites.fetch_invite_target_users_job_status(self.code, **kwargs)


class TargetUsersJobStatus(DiscordObject):
    """From `invite.fetch_target_users_job_status()`. `.status`,
    `.total_users`, `.processed_users`, `.created_at`, `.completed_at`,
    `.error_message`."""


class FollowedChannel(DiscordObject):
    """Returned by `channel.follow_announcement()`: the webhook created in
    the target channel to mirror this announcement channel's posts.
    `.channel_id`, `.webhook_id`."""


class MessagePin(DiscordObject):
    """One entry from `channel.fetch_pins()`. `.pinned_at` is an ISO 8601
    timestamp string of when it was pinned."""

    @property
    def message(self) -> Any:
        """The pinned `Message`."""
        message_data = self._data.get("message")
        return Message(message_data) if message_data is not None else None


class Ban(DiscordObject):
    """One entry from `guild.fetch_bans()`. `.reason`, `.user`."""

    @property
    def user(self) -> Any:
        """The banned `User`."""
        user_data = self._data.get("user")
        return User(user_data) if user_data is not None else None


class Integration(DiscordObject):
    """One entry from `guild.fetch_integrations()`. `.id`, `.name`, `.type`,
    `.enabled`, `.account`, and any other field Discord sends."""


class VoiceRegion(DiscordObject):
    """One entry from `guild.fetch_voice_regions()`. `.id`, `.name`,
    `.optimal`, `.deprecated`, `.custom`."""


class VoiceState(DiscordObject):
    """From `guild.fetch_voice_state()`/`guild.fetch_member_voice_state()`.
    `.channel_id`, `.session_id`, `.deaf`, `.mute`, `.self_deaf`,
    `.self_mute`, `.self_stream`, `.self_video`, `.suppress`,
    `.request_to_speak_timestamp`."""


class GuildWidgetSettings(DiscordObject):
    """From `guild.fetch_widget_settings()`/`guild.edit_widget()`.
    `.enabled`, `.channel_id`."""


class GuildWidget(DiscordObject):
    """From `guild.fetch_widget()`. `.id`, `.name`, `.instant_invite`,
    `.channels`, `.members`, `.presence_count`."""


class WelcomeScreen(DiscordObject):
    """From `guild.fetch_welcome_screen()`/`guild.edit_welcome_screen()`.
    `.description`, `.welcome_channels`."""


class GuildOnboarding(DiscordObject):
    """From `guild.fetch_onboarding()`/`guild.edit_onboarding()`.
    `.guild_id`, `.prompts`, `.default_channel_ids`, `.enabled`, `.mode`."""


class IncidentsData(DiscordObject):
    """From `guild.edit_incident_actions()`. `.invites_disabled_until`,
    `.dms_disabled_until`, `.dm_spam_detected_at`, `.raid_detected_at`."""


class BulkBanResult(DiscordObject):
    """From `guild.bulk_ban()`. `.banned_users` and `.failed_users` are
    both lists of user id strings."""


class MessageSearchResult(DiscordObject):
    """From `guild.search_messages()`. `.total_results`,
    `.doing_deep_historical_index`."""

    @property
    def messages(self) -> Any:
        """The matching messages, as a list of `Message`. Discord used to
        nest each hit in its own array to carry surrounding context, that
        context is no longer returned, so this flattens it back out."""
        return [Message(hit[0]) for hit in self._data.get("messages", []) if hit]

    @property
    def threads(self) -> Any:
        """Threads containing any of the matched messages, as a list of `Channel`."""
        return [Channel(c) for c in self._data.get("threads", [])]

    @property
    def members(self) -> Any:
        """A `ThreadMember` per thread in `.threads` the bot has joined."""
        return [ThreadMember(m) for m in self._data.get("members", [])]


class Webhook(DiscordObject):
    """A Discord webhook. `.id`, `.type`, `.name`, `.avatar`, `.channel_id`,
    `.guild_id`, `.token` (only present for Incoming Webhooks, e.g. right
    after `guild.create_webhook()`), and any other field Discord sends."""

    async def edit(self, **kwargs: Any) -> Any:
        """Update this webhook. Requires `MANAGE_WEBHOOKS`."""
        return await webhooks.edit_webhook(self.id, **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Delete this webhook. Requires `MANAGE_WEBHOOKS`."""
        await webhooks.delete_webhook(self.id, **kwargs)

    async def execute(
        self,
        content: Any = None,
        *,
        embeds: Any = None,
        components: Any = None,
        files: Any = None,
        username: str | None = None,
        avatar_url: str | None = None,
        tts: bool = False,
        allowed_mentions: Any = None,
        wait: bool = False,
        thread_id: str | None = None,
    ) -> Any:
        """Send a message through this webhook, authenticated with its own
        token rather than `DISCORD_BOT_TOKEN`. Only works on a `Webhook`
        that carries `.token` (Incoming Webhooks, e.g. straight after
        `guild.create_webhook()`)."""
        payload = _webhook.build_payload(
            content,
            embeds,
            components,
            username=username,
            avatar_url=avatar_url,
            tts=tts,
            allowed_mentions=allowed_mentions,
        )
        _, body = await asyncio.get_event_loop().run_in_executor(
            None, _webhook.execute, self.id, self.token, payload, files, wait, thread_id
        )
        if wait and body:
            return json.loads(body)

    async def fetch_message(self, message_id: str = "@original", **kwargs: Any) -> Any:
        """Fetch a message previously sent through this webhook. Uses its
        own token, not `DISCORD_BOT_TOKEN`."""
        _, body = await asyncio.get_event_loop().run_in_executor(
            None, _webhook.get_message, self.id, self.token, message_id
        )
        return json.loads(body)

    async def edit_message(
        self,
        message_id: str = "@original",
        content: Any = None,
        *,
        embeds: Any = None,
        components: Any = None,
        files: Any = None,
        allowed_mentions: Any = None,
    ) -> Any:
        """Edit a message previously sent through this webhook. Uses its
        own token, not `DISCORD_BOT_TOKEN`."""
        payload = _webhook.build_payload(content, embeds, components, allowed_mentions=allowed_mentions)
        await asyncio.get_event_loop().run_in_executor(
            None, _webhook.edit_message, self.id, self.token, message_id, payload, files
        )

    async def delete_message(self, message_id: str = "@original") -> Any:
        """Delete a message previously sent through this webhook. Uses its
        own token, not `DISCORD_BOT_TOKEN`."""
        await asyncio.get_event_loop().run_in_executor(None, _webhook.delete_message, self.id, self.token, message_id)


class Emoji(DiscordObject):
    """A custom emoji, from `guild.fetch_emojis()` or
    `bot.fetch_application_emojis()`. `.id`, `.name`, `.roles`, `.animated`,
    `.available`, and any other field Discord sends."""

    async def edit(self, **kwargs: Any) -> Any:
        """Update this emoji. Requires and
        `CREATE_GUILD_EXPRESSIONS`/`MANAGE_GUILD_EXPRESSIONS` for a guild
        emoji."""
        if "guild_id" in self._data:
            return await emojis.edit_guild_emoji(self._data["guild_id"], self.id, **kwargs)
        return await emojis.edit_application_emoji(self._data["application_id"], self.id, **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Delete this emoji. Requires and
        `CREATE_GUILD_EXPRESSIONS`/`MANAGE_GUILD_EXPRESSIONS` for a guild
        emoji."""
        if "guild_id" in self._data:
            await emojis.delete_guild_emoji(self._data["guild_id"], self.id, **kwargs)
        else:
            await emojis.delete_application_emoji(self._data["application_id"], self.id, **kwargs)


def _guild_id_or_raise(data: dict[str, Any], message: str) -> Any:
    """Shared guard for resources with a non-guild variant that can't be
    edited or deleted (pack stickers, default soundboard sounds, ...) -
    guild_id is only present on the guild-scoped kind."""
    try:
        return data["guild_id"]
    except KeyError:
        raise ValueError(message) from None


class Sticker(DiscordObject):
    """A sticker, from `guild.fetch_stickers()` or a message's
    `sticker_items`. `.id`, `.name`, `.description`, `.tags`, `.type`,
    `.format_type`, and any other field Discord sends. `.guild_id` is only
    present on guild stickers, not standard (pack) ones."""

    async def edit(self, **kwargs: Any) -> Any:
        """Update this guild sticker. Requires and
        `CREATE_GUILD_EXPRESSIONS`/`MANAGE_GUILD_EXPRESSIONS`."""
        guild_id = _guild_id_or_raise(self._data, "can't edit a sticker pack sticker, only guild stickers")
        return await stickers.edit_guild_sticker(guild_id, self.id, **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Delete this guild sticker. Requires and
        `CREATE_GUILD_EXPRESSIONS`/`MANAGE_GUILD_EXPRESSIONS`."""
        guild_id = _guild_id_or_raise(self._data, "can't delete a sticker pack sticker, only guild stickers")
        await stickers.delete_guild_sticker(guild_id, self.id, **kwargs)


class SoundboardSound(DiscordObject):
    """A soundboard sound, from `guild.fetch_soundboard_sounds()` or
    `bot.fetch_default_soundboard_sounds()`. Keyed by `.sound_id`, not
    `.id`. `.name`, `.volume`, `.emoji_id`, `.emoji_name`. `.guild_id` is
    only present on guild sounds, not default ones."""

    async def edit(self, **kwargs: Any) -> Any:
        """Update this guild soundboard sound. Requires `CREATE_GUILD_EXPRESSIONS`/
        `MANAGE_GUILD_EXPRESSIONS`."""
        guild_id = _guild_id_or_raise(self._data, "can't edit a default soundboard sound, only guild sounds")
        return await soundboard.edit_guild_soundboard_sound(guild_id, self.sound_id, **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Delete this guild soundboard sound. Requires `CREATE_GUILD_EXPRESSIONS`/
        `MANAGE_GUILD_EXPRESSIONS`."""
        guild_id = _guild_id_or_raise(self._data, "can't delete a default soundboard sound, only guild sounds")
        await soundboard.delete_guild_soundboard_sound(guild_id, self.sound_id, **kwargs)


class StickerPack(DiscordObject):
    """One of Discord's official sticker packs, from `bot.fetch_sticker_packs()`.
    `.id`, `.name`, `.description`, `.sku_id`, `.cover_sticker_id`,
    `.banner_asset_id`. `.stickers` is a list of `Sticker`."""

    @property
    def stickers(self) -> Any:
        return [Sticker(s) for s in self._data.get("stickers", [])]


class GuildScheduledEvent(DiscordObject):
    """A guild scheduled event, from `guild.fetch_scheduled_events()`.
    `.id`, `.guild_id`, `.name`, `.description`, `.scheduled_start_time`,
    `.status`, `.entity_type`, and any other field Discord sends."""

    @property
    def creator(self) -> Any:
        """The `User` that created this event, or `None` (always `None`
        for events created before 25 October 2021)."""
        creator_data = self._data.get("creator")
        return User(creator_data) if creator_data is not None else None

    async def edit(self, **kwargs: Any) -> Any:
        """Update this event. Set `status` to start/end it. Returns the
        updated `GuildScheduledEvent`."""
        return await scheduled_events.edit_guild_scheduled_event(self.guild_id, self.id, **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Requires MANAGE_EVENTS."""
        await scheduled_events.delete_guild_scheduled_event(self.guild_id, self.id, **kwargs)

    async def fetch_users(self, **kwargs: Any) -> Any:
        """List users subscribed to this event, as a list of
        `GuildScheduledEventUser`."""
        return await scheduled_events.fetch_guild_scheduled_event_users(self.guild_id, self.id, **kwargs)


class AutoModerationRule(DiscordObject):
    """An auto moderation rule, from `guild.fetch_auto_moderation_rules()`.
    `.id`, `.guild_id`, `.name`, `.creator_id`, `.event_type`,
    `.trigger_type`, `.trigger_metadata`, `.actions`, `.enabled`,
    `.exempt_roles`, `.exempt_channels`."""

    async def edit(self, **kwargs: Any) -> Any:
        """Update this rule. Returns the updated `AutoModerationRule`.
        Requires `MANAGE_GUILD`."""
        return await auto_moderation.edit_auto_moderation_rule(self.guild_id, self.id, **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Delete this rule. Requires `MANAGE_GUILD`."""
        await auto_moderation.delete_auto_moderation_rule(self.guild_id, self.id, **kwargs)


class GuildScheduledEventUser(DiscordObject):
    """One entry from `event.fetch_users()`. `.guild_scheduled_event_id`."""

    @property
    def user(self) -> Any:
        """The subscribed `User`."""
        user_data = self._data.get("user")
        return User(user_data) if user_data is not None else None

    @property
    def member(self) -> Any:
        """The subscribing `Member`, if included (`with_member=True`),
        else `None`."""
        member_data = self._data.get("member")
        return Member(_with_guild_id(member_data, self._data.get("guild_id"))) if member_data is not None else None


class StageInstance(DiscordObject):
    """A live Stage's instance, from `channel.fetch_stage_instance()` or
    `channel.create_stage_instance()`. `.id`, `.guild_id`, `.channel_id`,
    `.topic`, `.privacy_level`, `.guild_scheduled_event_id`."""

    async def edit(self, **kwargs: Any) -> Any:
        """Update this Stage instance. Returns the updated `StageInstance`.
        Requires Stage moderator permissions."""
        return await stage_instances.edit_stage_instance(self.channel_id, **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Delete this Stage instance. Requires Stage moderator permissions."""
        await stage_instances.delete_stage_instance(self.channel_id, **kwargs)


class GuildTemplate(DiscordObject):
    """A guild template, from `guild.fetch_templates()` or
    `bot.fetch_template()`. `.code`, `.name`, `.description`, `.usage_count`,
    `.creator_id`, `.source_guild_id`, `.serialized_source_guild`,
    `.is_dirty`. Keyed by `code`, not `id`."""

    @property
    def creator(self) -> Any:
        """The `User` who created this template."""
        creator_data = self._data.get("creator")
        return User(creator_data) if creator_data is not None else None

    async def sync(self, **kwargs: Any) -> Any:
        """Sync this template to its source guild's current state. Returns
        the updated `GuildTemplate`. Requires `MANAGE_GUILD`."""
        return await templates.sync_guild_template(self.source_guild_id, self.code, **kwargs)

    async def edit(self, **kwargs: Any) -> Any:
        """Update this template's name/description. Returns the updated
        `GuildTemplate`. Requires `MANAGE_GUILD`."""
        return await templates.edit_guild_template(self.source_guild_id, self.code, **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Delete this template. Returns the deleted `GuildTemplate`.
        Requires `MANAGE_GUILD`."""
        return await templates.delete_guild_template(self.source_guild_id, self.code, **kwargs)


class AuditLogEntry(DiscordObject):
    """One entry from `guild.fetch_audit_log()`. `.id`, `.user_id`,
    `.target_id`, `.action_type`, `.changes`, `.options`, `.reason`."""


class AuditLog(DiscordObject):
    """From `guild.fetch_audit_log()`. `.application_commands` and
    `.audit_log_entries` are raw dicts; the rest are wrapped in their usual
    model classes."""

    @property
    def entries(self) -> Any:
        return [AuditLogEntry(e) for e in self._data.get("audit_log_entries", [])]

    @property
    def users(self) -> Any:
        return [User(u) for u in self._data.get("users", [])]

    @property
    def webhooks(self) -> Any:
        return [Webhook(w) for w in self._data.get("webhooks", [])]

    @property
    def integrations(self) -> Any:
        return [Integration(i) for i in self._data.get("integrations", [])]

    @property
    def threads(self) -> Any:
        return [Thread(t) for t in self._data.get("threads", [])]

    @property
    def auto_moderation_rules(self) -> Any:
        return [AutoModerationRule(r) for r in self._data.get("auto_moderation_rules", [])]

    @property
    def guild_scheduled_events(self) -> Any:
        return [GuildScheduledEvent(e) for e in self._data.get("guild_scheduled_events", [])]


class Entitlement(DiscordObject):
    """From `bot.fetch_entitlements()`. `.id`, `.sku_id`, `.application_id`,
    `.user_id`, `.guild_id`, `.type`, `.deleted`, `.starts_at`, `.ends_at`,
    `.consumed`."""

    async def consume(self, **kwargs: Any) -> Any:
        """Mark this one-time-purchase consumable entitlement as consumed."""
        await entitlements.consume_entitlement(self.application_id, self.id, **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Test entitlements only; a real purchase can't be deleted this way."""
        await entitlements.delete_test_entitlement(self.application_id, self.id, **kwargs)


class SKU(DiscordObject):
    """From `bot.fetch_skus()`. `.id`, `.type`, `.application_id`, `.name`,
    `.slug`, `.flags`."""


class Subscription(DiscordObject):
    """A recurring premium purchase, from `bot.fetch_sku_subscriptions()`.
    `.id`, `.user_id`, `.sku_ids`, `.entitlement_ids`,
    `.current_period_start`, `.current_period_end`, `.status`,
    `.canceled_at`."""


class Application(DiscordObject):
    """The bot's own application, from `bot.fetch_application()`/
    `bot.edit_application()`. `.id`, `.name`, `.icon`, `.description`,
    `.bot_public`, `.flags`, `.tags`, `.install_params`,
    `.integration_types_config`, and any other field Discord sends."""

    async def edit(self, **kwargs: Any) -> Any:
        """Update the application's settings. Returns the updated
        `Application`."""
        return await application.edit_current_application(**kwargs)


class ApplicationRoleConnectionMetadata(DiscordObject):
    """One Linked Roles metadata record, from
    `bot.fetch_application_role_connection_metadata()`. `.type`, `.key`,
    `.name`, `.description`, and the optional `.name_localizations`/
    `.description_localizations` dicts. Edited as a full list via
    `bot.edit_application_role_connection_metadata()`, not per-record."""


class ApplicationCommand(DiscordObject):
    """From `bot.fetch_global_commands()`/`bot.fetch_guild_commands()`.
    `.id`, `.application_id`, `.guild_id` (only for guild-scoped commands),
    `.name`, `.description`, `.options`, `.type`, `.version`, and any other
    field Discord sends."""

    async def edit(self, **kwargs: Any) -> Any:
        """Update this command. Returns the updated `ApplicationCommand`."""
        guild_id = self._data.get("guild_id")
        if guild_id:
            return await application_commands.edit_guild_command(self.application_id, guild_id, self.id, **kwargs)
        return await application_commands.edit_global_command(self.application_id, self.id, **kwargs)

    async def delete(self, **kwargs: Any) -> Any:
        """Global commands take up to an hour to clear from every guild."""
        guild_id = self._data.get("guild_id")
        if guild_id:
            await application_commands.delete_guild_command(self.application_id, guild_id, self.id, **kwargs)
        else:
            await application_commands.delete_global_command(self.application_id, self.id, **kwargs)

    async def fetch_permissions(self, **kwargs: Any) -> Any:
        """Fetch this guild command's permissions. Guild-scoped commands
        only."""
        return await application_commands.fetch_command_permissions(
            self.application_id, self._data["guild_id"], self.id, **kwargs
        )


class GuildApplicationCommandPermissions(DiscordObject):
    """From `bot.fetch_command_permissions()`. `.id` (the command id),
    `.application_id`, `.guild_id`, `.permissions`."""


# Imported at the end to break the cycle: these resource modules import
# the model classes above. Every class is defined by this point.
from .. import webhook as _webhook
from .._payload import _with_guild_id
from ..models import Channel, Member, Message, User
from . import (
    application,
    application_commands,
    auto_moderation,
    emojis,
    entitlements,
    invites,
    scheduled_events,
    soundboard,
    stage_instances,
    stickers,
    templates,
    threads,
    webhooks,
)
