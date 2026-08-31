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

    def __repr__(self):
        return f"{type(self).__name__}(id={self._data.get('id')!r})"
