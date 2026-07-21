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
    """A Discord permission bitfield, e.g. `ctx.member.permissions`. Discord
    sends this as a plain string of a big int. Wraps it so callers can read
    named bits like `.administrator` or `.manage_guild` directly, instead of
    masking the raw value by hand."""

    def __init__(self, raw):
        self.value = int(raw or 0)

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
    def permissions(self):
        """This role's permissions, as a `Permissions` object
        (`.administrator`, `.manage_guild`, ...) instead of the raw
        bitfield string Discord sends."""
        raw = self._data.get("permissions")
        return Permissions(raw) if raw is not None else None


def _wrap(cls, data):
    return cls(data) if data is not None else None
