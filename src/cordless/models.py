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


def _wrap(cls, data):
    return cls(data) if data is not None else None
