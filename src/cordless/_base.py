"""DiscordObject: the attribute wrapper every response model builds on.

Kept in its own module so the REST model classes in _rest/models.py can
subclass it without importing models.py, which would pull in the resource
layer and close an import loop.
"""

from typing import Any, cast

__all__ = ["DiscordObject", "_wrap"]


class DiscordObject:
    """Thin attribute wrapper around a raw Discord API object."""

    def __init__(self, data: dict[str, Any] | None) -> None:
        self._data: dict[str, Any] = data or {}

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name) from None

    def to_dict(self) -> dict[str, Any]:
        """The raw Discord API object this wraps."""
        return self._data

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DiscordObject):
            return self._data == other._data
        if isinstance(other, dict):
            return self._data == other
        return NotImplemented

    def __hash__(self) -> int:
        # Defining __eq__ drops the default __hash__, which leaves every model
        # unhashable (no set(), no dict key). Hash on the id, or the nested
        # user id for a member payload, which carries none of its own. Equal
        # objects share these, so this stays consistent with __eq__; anything
        # without either just collides and falls back to __eq__.
        ident: Any = self._data.get("id")
        if ident is None:
            user = self._data.get("user")
            if isinstance(user, dict):
                ident = cast("dict[str, Any]", user).get("id")
        return hash(ident)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self._data.get('id')!r})"


def _wrap(cls: type[Any], data: Any) -> Any:
    """Build `cls(data)`, or `None` when `data` is absent."""
    return cls(data) if data is not None else None
