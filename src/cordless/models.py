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
    @property
    def display_name(self):
        return self._data.get("global_name") or self._data.get("username")

    @property
    def mention(self):
        return f"<@{self._data['id']}>"


class Member(DiscordObject):
    @property
    def user(self):
        user_data = self._data.get("user")
        return User(user_data) if user_data is not None else None

    @property
    def display_name(self):
        nick = self._data.get("nick")
        if nick:
            return nick
        user = self.user
        return user.display_name if user else None


class Message(DiscordObject):
    @property
    def author(self):
        author_data = self._data.get("author")
        return User(author_data) if author_data is not None else None


class Channel(DiscordObject):
    pass


class Attachment(DiscordObject):
    pass


def _wrap(cls, data):
    return cls(data) if data is not None else None
