"""DiscordObject: the attribute wrapper every response model builds on.

Kept in its own module so the REST model classes in _rest/models.py can
subclass it without importing models.py, which would pull in the resource
layer and close an import loop.
"""


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

    def __hash__(self):
        # Defining __eq__ drops the default __hash__, which leaves every model
        # unhashable (no set(), no dict key). Hash on the id, or the nested
        # user id for a member payload, which carries none of its own. Equal
        # objects share these, so this stays consistent with __eq__; anything
        # without either just collides and falls back to __eq__.
        ident = self._data.get("id")
        if ident is None:
            user = self._data.get("user")
            if isinstance(user, dict):
                ident = user.get("id")
        return hash(ident)

    def __repr__(self):
        return f"{type(self).__name__}(id={self._data.get('id')!r})"
