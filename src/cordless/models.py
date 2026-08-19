# bit values from Discord's permissions flags docs. new bits get added
# there occasionally, check against the current docs before adding one.
_PERMISSION_BITS = {
    "create_instant_invite": 0x1,
    "kick_members": 0x2,
    "ban_members": 0x4,
    "administrator": 0x8,
    "manage_channels": 0x10,
    "manage_guild": 0x20,
    "add_reactions": 0x40,
    "view_audit_log": 0x80,
    "priority_speaker": 0x100,
    "stream": 0x200,
    "view_channel": 0x400,
    "send_messages": 0x800,
    "send_tts_messages": 0x1000,
    "manage_messages": 0x2000,
    "embed_links": 0x4000,
    "attach_files": 0x8000,
    "read_message_history": 0x10000,
    "mention_everyone": 0x20000,
    "use_external_emojis": 0x40000,
    "view_guild_insights": 0x80000,
    "connect": 0x100000,
    "speak": 0x200000,
    "mute_members": 0x400000,
    "deafen_members": 0x800000,
    "move_members": 0x1000000,
    "use_vad": 0x2000000,
    "change_nickname": 0x4000000,
    "manage_nicknames": 0x8000000,
    "manage_roles": 0x10000000,
    "manage_webhooks": 0x20000000,
    "manage_guild_expressions": 0x40000000,
    "use_application_commands": 0x80000000,
    "request_to_speak": 0x100000000,
    "manage_events": 0x200000000,
    "manage_threads": 0x400000000,
    "create_public_threads": 0x800000000,
    "create_private_threads": 0x1000000000,
    "use_external_stickers": 0x2000000000,
    "send_messages_in_threads": 0x4000000000,
    "use_embedded_activities": 0x8000000000,
    "moderate_members": 0x10000000000,
    "view_creator_monetization_analytics": 0x20000000000,
    "use_soundboard": 0x40000000000,
    "create_guild_expressions": 0x80000000000,
    "create_events": 0x100000000000,
    "use_external_sounds": 0x200000000000,
    "send_voice_messages": 0x400000000000,
    "send_polls": 0x2000000000000,
    "use_external_apps": 0x4000000000000,
}


class Permissions:
    """A Discord permission bitfield. Read one off an incoming member or
    role, e.g. `ctx.member.permissions.manage_guild`, or build one to send,
    e.g. `default_member_permissions=Permissions(manage_guild=True)`.

    `raw` is the starting value (Discord sends this as a string of a big
    int, e.g. off `ctx.member.permissions` or `ctx.role.permissions`).
    Keyword args set or clear individual named bits on top of that, e.g.
    `Permissions(manage_guild=True, kick_members=True)`."""

    def __init__(self, raw=0, **flags):
        self.value = int(raw or 0)
        for name, on in flags.items():
            if name not in _PERMISSION_BITS:
                raise TypeError(f"unknown permission: {name!r}")
            bit = _PERMISSION_BITS[name]
            self.value = (self.value | bit) if on else (self.value & ~bit)

    def __getattr__(self, name):
        try:
            bit = _PERMISSION_BITS[name]
        except KeyError:
            raise AttributeError(name) from None
        return bool(self.value & bit)

    def __int__(self):
        return self.value

    def __repr__(self):
        return f"Permissions({self.value})"


_CDN_BASE = "https://cdn.discordapp.com"


def _cdn_asset_url(path, image_hash):
    """Discord CDN URL for an asset hash. `path` already has the owning
    id baked in (e.g. "avatars/123/{hash}"); hashes prefixed "a_" are
    animated and served as .gif, everything else as .png."""
    if not image_hash:
        return None
    ext = "gif" if image_hash.startswith("a_") else "png"
    return f"{_CDN_BASE}/{path.format(hash=image_hash)}.{ext}"


class DiscordObject:
    """Thin attribute wrapper around a raw Discord API object."""

    def __init__(self, data):
        self._data = data or {}

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name) from None

    def __eq__(self, other):
        if isinstance(other, DiscordObject):
            return self._data == other._data
        if isinstance(other, dict):
            return self._data == other
        return NotImplemented

    def __repr__(self):
        return f"{type(self).__name__}(id={self._data.get('id')!r})"


class User(DiscordObject):
    """A Discord user, e.g. `ctx.user`. `.id`, `.username`, `.global_name`,
    `.bot`, and any other field Discord sends are available as attributes -
    not modeled explicitly here, since they're resolved dynamically off the
    raw payload by `DiscordObject.__getattr__`."""

    @property
    def display_name(self):
        """`global_name`, falling back to `username`."""
        return self._data.get("global_name") or self._data.get("username")

    @property
    def mention(self):
        """`<@id>`, Discord's mention syntax for this user."""
        return f"<@{self._data['id']}>"

    @property
    def avatar_url(self):
        """Full CDN URL for this user's avatar. Falls back to one of
        Discord's default avatars (indexed off the user id, or the
        discriminator for pre-migration accounts) when no custom avatar
        is set."""
        user_id = self._data.get("id")
        avatar = self._data.get("avatar")
        if avatar and user_id:
            return _cdn_asset_url(f"avatars/{user_id}/{{hash}}", avatar)
        if not user_id:
            return None
        discriminator = self._data.get("discriminator")
        index = int(discriminator) % 5 if discriminator and discriminator != "0" else (int(user_id) >> 22) % 6
        return f"{_CDN_BASE}/embed/avatars/{index}.png"

    @property
    def banner_url(self):
        """Full CDN URL for this user's profile banner, or `None` if
        they don't have one set."""
        user_id = self._data.get("id")
        banner = self._data.get("banner")
        return _cdn_asset_url(f"banners/{user_id}/{{hash}}", banner) if user_id else None


class Member(DiscordObject):
    """A guild member, e.g. `ctx.member` (`None` in DMs). `.nick`, `.roles`,
    `.permissions`, and any other field Discord sends are available as
    attributes."""

    @property
    def user(self):
        """The member's underlying `User`."""
        user_data = self._data.get("user")
        return User(user_data) if user_data is not None else None

    @property
    def display_name(self):
        """`nick`, falling back to the user's own `display_name`."""
        nick = self._data.get("nick")
        if nick:
            return nick
        user = self.user
        return user.display_name if user else None

    @property
    def permissions(self):
        """This member's permissions, as a `Permissions` object
        (`.administrator`, `.manage_guild`, ...) instead of the raw
        bitfield string Discord sends."""
        raw = self._data.get("permissions")
        return Permissions(raw) if raw is not None else None


class Message(DiscordObject):
    """A Discord message, e.g. `ctx.message` (the message a component sits
    on). `.id`, `.content`, `.embeds`, and any other field Discord sends are
    available as attributes."""

    @property
    def author(self):
        """The message's sender, as a `User`."""
        author_data = self._data.get("author")
        return User(author_data) if author_data is not None else None


class Channel(DiscordObject):
    """A partial Discord channel, e.g. `ctx.channel`. `.id`, `.name`,
    `.type`, and any other field Discord sends are available as
    attributes."""

    @property
    def mention(self):
        """`<#id>`, Discord's mention syntax for this channel."""
        return f"<#{self._data['id']}>"

    async def start_thread_from_message(self, message_id, name, **kwargs):
        """Start a thread off an existing message in this channel. Returns
        a `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.start_thread_from_message(self.id, message_id, name, **kwargs)

    async def start_thread_without_message(self, name, **kwargs):
        """Start a thread not attached to any message in this channel.
        Returns a `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.start_thread_without_message(self.id, name, **kwargs)

    async def start_thread_from_forum(self, name, *, message, **kwargs):
        """Start a forum post (a thread with its first message) in this
        forum channel. Returns a `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.start_thread_from_forum(self.id, name, message=message, **kwargs)

    async def fetch_public_archived_threads(self, **kwargs):
        """List this channel's public archived threads, as a list of
        `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.fetch_public_archived_threads(self.id, **kwargs)

    async def fetch_private_archived_threads(self, **kwargs):
        """List this channel's private archived threads, as a list of
        `Thread`. Requires `DISCORD_BOT_TOKEN` and `MANAGE_THREADS`."""
        from ._rest import threads

        return await threads.fetch_private_archived_threads(self.id, **kwargs)

    async def fetch_joined_private_archived_threads(self, **kwargs):
        """List this channel's private archived threads the bot has joined,
        as a list of `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.fetch_joined_private_archived_threads(self.id, **kwargs)


class Attachment(DiscordObject):
    """A file attached to a command's `attachment` option, e.g.
    `ctx.attachments[att_id]`. `.id`, `.filename`, `.url`, `.size`,
    `.content_type`, and any other field Discord sends are available as
    attributes."""


class Role(DiscordObject):
    """A Discord role, e.g. `ctx.resolved_roles[role_id]` from a `RoleSelect`
    or `MentionableSelect` pick. `.id`, `.name`, `.color`, `.permissions`,
    and any other field Discord sends are available as attributes."""

    @property
    def mention(self):
        """`<@&id>`, Discord's mention syntax for this role."""
        return f"<@&{self._data['id']}>"

    @property
    def icon_url(self):
        """Full CDN URL for this role's custom icon, or `None` if it
        doesn't have one (roles that use an emoji instead of an
        uploaded icon don't have one)."""
        role_id = self._data.get("id")
        icon = self._data.get("icon")
        return _cdn_asset_url(f"role-icons/{role_id}/{{hash}}", icon) if role_id else None

    @property
    def permissions(self):
        """This role's permissions, as a `Permissions` object
        (`.administrator`, `.manage_guild`, ...) instead of the raw
        bitfield string Discord sends."""
        raw = self._data.get("permissions")
        return Permissions(raw) if raw is not None else None


class Guild(DiscordObject):
    """A Discord guild, e.g. `ctx.guild`. Built from the partial guild object
    Discord includes on the interaction, so most fields beyond `.id`,
    `.locale`, and `.features` are not present here."""

    @property
    def icon_url(self):
        """Full CDN URL for this guild's icon, or `None` if unset."""
        guild_id = self._data.get("id")
        icon = self._data.get("icon")
        return _cdn_asset_url(f"icons/{guild_id}/{{hash}}", icon) if guild_id else None

    @property
    def banner_url(self):
        """Full CDN URL for this guild's banner, or `None` if unset."""
        guild_id = self._data.get("id")
        banner = self._data.get("banner")
        return _cdn_asset_url(f"banners/{guild_id}/{{hash}}", banner) if guild_id else None

    @property
    def splash_url(self):
        """Full CDN URL for this guild's invite splash, or `None` if unset."""
        guild_id = self._data.get("id")
        splash = self._data.get("splash")
        return _cdn_asset_url(f"splashes/{guild_id}/{{hash}}", splash) if guild_id else None

    @property
    def discovery_splash_url(self):
        """Full CDN URL for this guild's discovery splash, or `None` if
        unset."""
        guild_id = self._data.get("id")
        splash = self._data.get("discovery_splash")
        return _cdn_asset_url(f"discovery-splashes/{guild_id}/{{hash}}", splash) if guild_id else None

    async def fetch_active_threads(self, **kwargs):
        """List every active thread in this guild (public and private), as
        a list of `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.fetch_active_guild_threads(self.id, **kwargs)


def _wrap(cls, data):
    return cls(data) if data is not None else None
