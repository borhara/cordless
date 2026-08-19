"""Shared dataclasses for REST responses.

Carry read-only convenience properties plus thin action methods (e.g.
thread.join()), but never a back-reference to a Cordless instance. Each
action method is a straight delegation to the same _rest/<resource>.py
function bot.<verb>_<resource>() already calls, using only this object's own
id and, optionally, an explicit token kwarg - both call shapes hit the exact
same code path, so there is no request logic duplicated between them.
"""

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
