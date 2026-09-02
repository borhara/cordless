"""Discord embed builder."""

from datetime import datetime
from typing import Any, Self


class EmbedField:
    """What `Embed.add_field` creates; you rarely construct it directly."""

    def __init__(self, name: str, value: str, inline: bool = False) -> None:
        self.name = name
        self.value = value
        self.inline = inline

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "value": self.value}
        if self.inline:
            d["inline"] = True
        return d


class Embed:
    """`color` is an integer (`0x5865F2`); `timestamp` accepts a `datetime`
    or ISO 8601 string. All setters return the embed, so calls chain:
    `Embed(title="Hi").set_footer("a footer").add_field("name", "value")`."""

    def __init__(
        self,
        title: str | None = None,
        description: str | None = None,
        color: int | None = None,
        url: str | None = None,
        timestamp: datetime | str | None = None,
    ) -> None:
        self.title = title
        self.description = description
        self.color = color
        self.url = url
        self.timestamp = timestamp
        self._footer: dict[str, str] | None = None
        self._image: dict[str, str] | None = None
        self._thumbnail: dict[str, str] | None = None
        self._author: dict[str, str] | None = None
        self._fields: list[EmbedField] = []

    def set_footer(self, text: str, icon_url: str | None = None) -> Self:
        """Sets the embed's footer text and optional icon. Returns self."""
        self._footer = {"text": text}
        if icon_url is not None:
            self._footer["icon_url"] = icon_url
        return self

    def set_image(self, url: str) -> Self:
        """Sets the embed's large image. Returns self."""
        self._image = {"url": url}
        return self

    def set_thumbnail(self, url: str) -> Self:
        """Sets the embed's small corner thumbnail. Returns self."""
        self._thumbnail = {"url": url}
        return self

    def set_author(self, name: str, url: str | None = None, icon_url: str | None = None) -> Self:
        """Sets the embed's author line, with an optional link and icon.
        Returns self."""
        self._author = {"name": name}
        if url is not None:
            self._author["url"] = url
        if icon_url is not None:
            self._author["icon_url"] = icon_url
        return self

    def add_field(self, name: str, value: str, inline: bool = False) -> Self:
        """Appends an `EmbedField`. Returns self."""
        self._fields.append(EmbedField(name, value, inline))
        return self

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.title is not None:
            d["title"] = self.title
        if self.description is not None:
            d["description"] = self.description
        if self.color is not None:
            d["color"] = self.color
        if self.url is not None:
            d["url"] = self.url
        if self.timestamp is not None:
            ts = self.timestamp
            d["timestamp"] = ts.isoformat() if isinstance(ts, datetime) else ts
        if self._footer is not None:
            d["footer"] = self._footer
        if self._image is not None:
            d["image"] = self._image
        if self._thumbnail is not None:
            d["thumbnail"] = self._thumbnail
        if self._author is not None:
            d["author"] = self._author
        if self._fields:
            d["fields"] = [f.to_dict() for f in self._fields]
        return d
