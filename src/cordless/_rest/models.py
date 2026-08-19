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
from dataclasses import Field, dataclass, field
from typing import ClassVar

from ..models import DiscordObject


class _FromDict:
    """Parses only known fields; ignores whatever new keys Discord adds later
    instead of raising, so a schema addition doesn't break existing bots."""

    # Declares the contract every subclass must satisfy (being an actual
    # @dataclass) so pyright can see __dataclass_fields__ below, since
    # _FromDict itself isn't decorated with @dataclass.
    __dataclass_fields__: ClassVar[dict[str, Field]]

    @classmethod
    def from_dict(cls, data):
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class ThreadMember(_FromDict):
    id: str | None = None
    user_id: str | None = None
    join_timestamp: str | None = None
    flags: int = 0


@dataclass
class Thread(_FromDict):
    id: str
    guild_id: str | None
    parent_id: str | None
    owner_id: str | None
    name: str
    type: int
    message_count: int = 0
    member_count: int = 0
    thread_metadata: dict = field(default_factory=dict)
    rate_limit_per_user: int = 0

    @property
    def archived(self):
        return self.thread_metadata.get("archived", False)

    @property
    def locked(self):
        return self.thread_metadata.get("locked", False)

    @property
    def mention(self):
        return f"<#{self.id}>"

    async def join(self, *, token=None):
        """Join this thread as the bot. Requires `DISCORD_BOT_TOKEN`."""
        from . import threads

        await threads.join_thread(self.id, token=token)

    async def leave(self, *, token=None):
        """Leave this thread. Requires `DISCORD_BOT_TOKEN`."""
        from . import threads

        await threads.leave_thread(self.id, token=token)

    async def add_member(self, user_id, *, token=None):
        """Add a member to this thread. Requires `DISCORD_BOT_TOKEN`."""
        from . import threads

        await threads.add_thread_member(self.id, user_id, token=token)

    async def remove_member(self, user_id, *, token=None):
        """Remove a member from this thread. Requires `DISCORD_BOT_TOKEN`."""
        from . import threads

        await threads.remove_thread_member(self.id, user_id, token=token)

    async def fetch_member(self, user_id, *, with_member=False, token=None):
        """Fetch a single member of this thread, as a `ThreadMember`.
        Requires `DISCORD_BOT_TOKEN`."""
        from . import threads

        return await threads.fetch_thread_member(self.id, user_id, with_member=with_member, token=token)

    async def fetch_members(self, *, with_member=False, token=None):
        """List this thread's members, as a list of `ThreadMember`. Requires
        `DISCORD_BOT_TOKEN`."""
        from . import threads

        return await threads.fetch_thread_members(self.id, with_member=with_member, token=token)


class Invite(DiscordObject):
    """A Discord invite, e.g. from `channel.fetch_invites()` or
    `channel.create_invite()`. `.code`, `.guild`, `.channel`, `.inviter`,
    `.uses`, `.max_uses`, `.max_age`, `.temporary`, and any other field
    Discord sends are available as attributes."""

    @property
    def url(self):
        """Full `https://discord.gg/<code>` invite link."""
        return f"https://discord.gg/{self._data['code']}"

    async def fetch(self, **kwargs):
        """Re-fetch this invite by code. Returns the refreshed `Invite`."""
        from . import invites

        return await invites.fetch_invite(self.code, **kwargs)

    async def delete(self, **kwargs):
        """Delete this invite. Returns the now-deleted `Invite`. Requires
        `DISCORD_BOT_TOKEN` and `MANAGE_CHANNELS` (or `MANAGE_GUILD` to
        remove any invite in the guild)."""
        from . import invites

        return await invites.delete_invite(self.code, **kwargs)


class FollowedChannel(DiscordObject):
    """Returned by `channel.follow_announcement()`: the webhook created in
    the target channel to mirror this announcement channel's posts.
    `.channel_id`, `.webhook_id`."""


class MessagePin(DiscordObject):
    """One entry from `channel.fetch_pins()`. `.pinned_at` is an ISO 8601
    timestamp string of when it was pinned."""

    @property
    def message(self):
        """The pinned `Message`."""
        from ..models import Message

        return Message(self._data.get("message"))


class Ban(DiscordObject):
    """One entry from `guild.fetch_bans()`. `.reason`, `.user`."""

    @property
    def user(self):
        """The banned `User`."""
        from ..models import User

        return User(self._data.get("user"))


class Integration(DiscordObject):
    """One entry from `guild.fetch_integrations()`. `.id`, `.name`, `.type`,
    `.enabled`, `.account`, and any other field Discord sends."""


class VoiceRegion(DiscordObject):
    """One entry from `guild.fetch_voice_regions()`. `.id`, `.name`,
    `.optimal`, `.deprecated`, `.custom`."""


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
    def messages(self):
        """The matching messages, as a list of `Message`. Discord used to
        nest each hit in its own array to carry surrounding context, that
        context is no longer returned, so this flattens it back out."""
        from ..models import Message

        return [Message(hit[0]) for hit in self._data.get("messages", []) if hit]

    @property
    def threads(self):
        """Threads containing any of the matched messages, as a list of `Channel`."""
        from ..models import Channel

        return [Channel(c) for c in self._data.get("threads", [])]

    @property
    def members(self):
        """A `ThreadMember` per thread in `.threads` the bot has joined."""
        return [ThreadMember.from_dict(m) for m in self._data.get("members", [])]


class Webhook(DiscordObject):
    """A Discord webhook. `.id`, `.type`, `.name`, `.avatar`, `.channel_id`,
    `.guild_id`, `.token` (only present for Incoming Webhooks, e.g. right
    after `guild.create_webhook()`), and any other field Discord sends."""

    async def edit(self, **kwargs):
        """Update this webhook. Requires `DISCORD_BOT_TOKEN` and `MANAGE_WEBHOOKS`."""
        from . import webhooks

        return await webhooks.edit_webhook(self.id, **kwargs)

    async def delete(self, **kwargs):
        """Delete this webhook. Requires `DISCORD_BOT_TOKEN` and `MANAGE_WEBHOOKS`."""
        from . import webhooks

        await webhooks.delete_webhook(self.id, **kwargs)

    async def execute(
        self,
        content=None,
        *,
        embeds=None,
        components=None,
        files=None,
        username=None,
        avatar_url=None,
        tts=False,
        allowed_mentions=None,
        wait=False,
        thread_id=None,
    ):
        """Send a message through this webhook, authenticated with its own
        token rather than `DISCORD_BOT_TOKEN`. Only works on a `Webhook`
        that carries `.token` (Incoming Webhooks, e.g. straight after
        `guild.create_webhook()`)."""
        from .. import webhook as _webhook

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

    async def fetch_message(self, message_id="@original", **kwargs):
        """Fetch a message previously sent through this webhook. Uses its
        own token, not `DISCORD_BOT_TOKEN`."""
        from .. import webhook as _webhook

        _, body = await asyncio.get_event_loop().run_in_executor(
            None, _webhook.get_message, self.id, self.token, message_id
        )
        return json.loads(body)

    async def edit_message(
        self, message_id="@original", content=None, *, embeds=None, components=None, files=None, allowed_mentions=None
    ):
        """Edit a message previously sent through this webhook. Uses its
        own token, not `DISCORD_BOT_TOKEN`."""
        from .. import webhook as _webhook

        payload = _webhook.build_payload(content, embeds, components, allowed_mentions=allowed_mentions)
        await asyncio.get_event_loop().run_in_executor(
            None, _webhook.edit_message, self.id, self.token, message_id, payload, files
        )

    async def delete_message(self, message_id="@original"):
        """Delete a message previously sent through this webhook. Uses its
        own token, not `DISCORD_BOT_TOKEN`."""
        from .. import webhook as _webhook

        await asyncio.get_event_loop().run_in_executor(None, _webhook.delete_message, self.id, self.token, message_id)


class Emoji(DiscordObject):
    """A custom emoji, from `guild.fetch_emojis()` or
    `bot.fetch_application_emojis()`. `.id`, `.name`, `.roles`, `.animated`,
    `.available`, and any other field Discord sends."""

    async def edit(self, **kwargs):
        """Update this emoji. Requires `DISCORD_BOT_TOKEN`, and
        `CREATE_GUILD_EXPRESSIONS`/`MANAGE_GUILD_EXPRESSIONS` for a guild
        emoji."""
        from . import emojis

        if "guild_id" in self._data:
            return await emojis.edit_guild_emoji(self._data["guild_id"], self.id, **kwargs)
        return await emojis.edit_application_emoji(self._data["application_id"], self.id, **kwargs)

    async def delete(self, **kwargs):
        """Delete this emoji. Requires `DISCORD_BOT_TOKEN`, and
        `CREATE_GUILD_EXPRESSIONS`/`MANAGE_GUILD_EXPRESSIONS` for a guild
        emoji."""
        from . import emojis

        if "guild_id" in self._data:
            await emojis.delete_guild_emoji(self._data["guild_id"], self.id, **kwargs)
        else:
            await emojis.delete_application_emoji(self._data["application_id"], self.id, **kwargs)


class Sticker(DiscordObject):
    """A sticker, from `guild.fetch_stickers()` or a message's
    `sticker_items`. `.id`, `.name`, `.description`, `.tags`, `.type`,
    `.format_type`, and any other field Discord sends. `.guild_id` is only
    present on guild stickers, not standard (pack) ones."""

    async def edit(self, **kwargs):
        """Update this guild sticker. Requires `DISCORD_BOT_TOKEN`, and
        `CREATE_GUILD_EXPRESSIONS`/`MANAGE_GUILD_EXPRESSIONS`."""
        from . import stickers

        return await stickers.edit_guild_sticker(self._data["guild_id"], self.id, **kwargs)

    async def delete(self, **kwargs):
        """Delete this guild sticker. Requires `DISCORD_BOT_TOKEN`, and
        `CREATE_GUILD_EXPRESSIONS`/`MANAGE_GUILD_EXPRESSIONS`."""
        from . import stickers

        await stickers.delete_guild_sticker(self._data["guild_id"], self.id, **kwargs)


class StickerPack(DiscordObject):
    """One of Discord's official sticker packs, from `bot.fetch_sticker_packs()`.
    `.id`, `.name`, `.description`, `.sku_id`, `.cover_sticker_id`,
    `.banner_asset_id`. `.stickers` is a list of `Sticker`."""

    @property
    def stickers(self):
        return [Sticker(s) for s in self._data.get("stickers", [])]


class GuildScheduledEvent(DiscordObject):
    """A guild scheduled event, from `guild.fetch_scheduled_events()`.
    `.id`, `.guild_id`, `.name`, `.description`, `.scheduled_start_time`,
    `.status`, `.entity_type`, and any other field Discord sends."""

    @property
    def creator(self):
        """The `User` that created this event, or `None` (always `None`
        for events created before 25 October 2021)."""
        from ..models import User

        creator_data = self._data.get("creator")
        return User(creator_data) if creator_data is not None else None

    async def edit(self, **kwargs):
        """Update this event. Set `status` to start/end it. Returns the
        updated `GuildScheduledEvent`. Requires `DISCORD_BOT_TOKEN`."""
        from . import scheduled_events

        return await scheduled_events.edit_guild_scheduled_event(self.guild_id, self.id, **kwargs)

    async def delete(self, **kwargs):
        """Delete this event. Requires `DISCORD_BOT_TOKEN`."""
        from . import scheduled_events

        await scheduled_events.delete_guild_scheduled_event(self.guild_id, self.id, **kwargs)

    async def fetch_users(self, **kwargs):
        """List users subscribed to this event, as a list of
        `GuildScheduledEventUser`. Requires `DISCORD_BOT_TOKEN`."""
        from . import scheduled_events

        return await scheduled_events.fetch_guild_scheduled_event_users(self.guild_id, self.id, **kwargs)


class GuildScheduledEventUser(DiscordObject):
    """One entry from `event.fetch_users()`. `.guild_scheduled_event_id`."""

    @property
    def user(self):
        """The subscribed `User`."""
        from ..models import User

        return User(self._data.get("user"))

    @property
    def member(self):
        """The subscribing `Member`, if included (`with_member=True`),
        else `None`."""
        from ..models import Member

        member_data = self._data.get("member")
        return Member(member_data) if member_data is not None else None
