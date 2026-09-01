# pyright: strict
"""Discord UI component builders."""

from collections.abc import Iterable
from typing import Any


class _ButtonStyle:
    """`Button.style` values: `PRIMARY` (1), `SECONDARY` (2), `SUCCESS` (3),
    `DANGER` (4), `LINK` (5, takes `url` instead of `custom_id`), `PREMIUM`
    (6, takes only `sku_id`)."""

    PRIMARY = 1
    SECONDARY = 2
    SUCCESS = 3
    DANGER = 4
    LINK = 5
    PREMIUM = 6


ButtonStyle = _ButtonStyle()


class SelectOption:
    """One option in a `StringSelect`. `default=True` pre-selects it."""

    def __init__(
        self,
        label: str,
        value: str,
        description: str | None = None,
        emoji: dict[str, Any] | None = None,
        default: bool = False,
    ) -> None:
        self.label = label
        self.value = value
        self.description = description
        self.emoji = emoji
        self.default = default

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"label": self.label, "value": self.value}
        if self.description is not None:
            d["description"] = self.description
        if self.emoji is not None:
            d["emoji"] = self.emoji
        if self.default:
            d["default"] = True
        return d


class Button:
    """`style` is a `ButtonStyle`. `emoji` is a partial emoji dict, e.g.
    `{"name": "👋"}` or `{"id": "1234", "name": "custom"}`."""

    def __init__(
        self,
        label: str | None = None,
        custom_id: str | None = None,
        style: int = 1,
        url: str | None = None,
        emoji: dict[str, Any] | None = None,
        disabled: bool = False,
        sku_id: str | None = None,
    ) -> None:
        self.label = label
        self.custom_id = custom_id
        self.style = style
        self.url = url
        self.emoji = emoji
        self.disabled = disabled
        self.sku_id = sku_id  # required for style=6 (PREMIUM) buttons

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": 2, "style": self.style}
        # premium buttons (style 6) only take sku_id, no label/custom_id/url
        if self.style == 6:
            if self.sku_id is not None:
                d["sku_id"] = self.sku_id
            return d
        if self.label is not None:
            d["label"] = self.label
        if self.custom_id is not None:
            d["custom_id"] = self.custom_id
        if self.url is not None:
            d["url"] = self.url
        if self.emoji is not None:
            d["emoji"] = self.emoji
        if self.disabled:
            d["disabled"] = True
        return d


class ActionRow:
    """Wraps up to 5 buttons, or exactly 1 select (Discord doesn't allow a
    select menu to share a row with anything else)."""

    def __init__(self, components: Iterable[Any]) -> None:
        components = list(components)
        if any(isinstance(c, (StringSelect, _EntitySelect)) for c in components):
            if len(components) > 1:
                raise ValueError("An ActionRow can only hold a single select menu, not alongside other components")
        elif len(components) > 5:
            raise ValueError(f"An ActionRow can hold at most 5 buttons, got {len(components)}")
        self.components = components

    def to_dict(self) -> dict[str, Any]:
        return {"type": 1, "components": [c.to_dict() for c in self.components]}


class StringSelect:
    """A select menu with a fixed list of `SelectOption`s."""

    def __init__(
        self,
        custom_id: str,
        options: Iterable[Any],
        placeholder: str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
    ) -> None:
        self.custom_id = custom_id
        self.options = options
        self.placeholder = placeholder
        self.min_values = min_values
        self.max_values = max_values
        self.disabled = disabled

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": 3,
            "custom_id": self.custom_id,
            "options": [o.to_dict() if hasattr(o, "to_dict") else o for o in self.options],
            "min_values": self.min_values,
            "max_values": self.max_values,
        }
        if self.placeholder is not None:
            d["placeholder"] = self.placeholder
        if self.disabled:
            d["disabled"] = True
        return d


class _EntitySelect:
    _type: int | None = None

    def __init__(
        self,
        custom_id: str,
        placeholder: str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        default_values: list[Any] | None = None,
    ) -> None:
        self.custom_id = custom_id
        self.placeholder = placeholder
        self.min_values = min_values
        self.max_values = max_values
        self.disabled = disabled
        self.default_values = default_values

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self._type,
            "custom_id": self.custom_id,
            "min_values": self.min_values,
            "max_values": self.max_values,
        }
        if self.placeholder is not None:
            d["placeholder"] = self.placeholder
        if self.disabled:
            d["disabled"] = True
        if self.default_values is not None:
            d["default_values"] = self.default_values
        return d


class UserSelect(_EntitySelect):
    """A select menu populated with the guild's members, resolved by
    Discord. `default_values` pre-selects entries: a list of
    `{"id": ..., "type": "user"}` dicts."""

    _type = 5


class RoleSelect(_EntitySelect):
    """A select menu populated with the guild's roles, resolved by
    Discord. `default_values` pre-selects entries: a list of
    `{"id": ..., "type": "role"}` dicts."""

    _type = 6


class MentionableSelect(_EntitySelect):
    """A select menu populated with both members and roles, resolved by
    Discord. `default_values` pre-selects entries: a list of
    `{"id": ..., "type": "user"|"role"}` dicts."""

    _type = 7


class ChannelSelect(_EntitySelect):
    """A select menu populated with the guild's channels, resolved by
    Discord. `channel_types` is a list of Discord channel type ints, e.g.
    `[0, 2]` for text + voice. `default_values` pre-selects entries: a list
    of `{"id": ..., "type": "channel"}` dicts."""

    _type = 8

    def __init__(
        self,
        custom_id: str,
        channel_types: list[int] | None = None,
        placeholder: str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        default_values: list[Any] | None = None,
    ) -> None:
        super().__init__(custom_id, placeholder, min_values, max_values, disabled, default_values)
        self.channel_types = channel_types

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        if self.channel_types is not None:
            d["channel_types"] = self.channel_types
        return d


class _TextInputStyle:
    """`TextInput.style` values: `SHORT` (1) or `PARAGRAPH` (2)."""

    SHORT = 1
    PARAGRAPH = 2


TextInputStyle = _TextInputStyle()


class TextInput:
    """A field inside a `Modal`. `value` pre-fills it."""

    def __init__(
        self,
        custom_id: str,
        label: str,
        style: int = 1,
        min_length: int | None = None,
        max_length: int | None = None,
        required: bool = True,
        value: str | None = None,
        placeholder: str | None = None,
    ) -> None:
        self.custom_id = custom_id
        self.label = label
        self.style = style
        self.min_length = min_length
        self.max_length = max_length
        self.required = required
        self.value = value
        self.placeholder = placeholder

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": 4, "custom_id": self.custom_id, "label": self.label, "style": self.style}
        if self.min_length is not None:
            d["min_length"] = self.min_length
        if self.max_length is not None:
            d["max_length"] = self.max_length
        if not self.required:
            d["required"] = False
        if self.value is not None:
            d["value"] = self.value
        if self.placeholder is not None:
            d["placeholder"] = self.placeholder
        return d


class Label:
    """Wraps a single select menu (or `TextInput`) in a `Modal` with a
    label, Discord's required container for anything other than a plain
    `TextInput` in an `ActionRow`."""

    def __init__(self, label: str, component: Any, description: str | None = None) -> None:
        self.label = label
        self.component = component
        self.description = description

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": 18, "label": self.label, "component": self.component.to_dict()}
        if self.description is not None:
            d["description"] = self.description
        return d


class Modal:
    """Takes up to 5 `TextInput`s (each wrapped in its own row automatically).
    Select menus aren't valid inside an `ActionRow` in a modal, wrap them in
    a `Label` first: `Modal("m", "Title", Label("Pick one", StringSelect(...)))`."""

    def __init__(self, custom_id: str, title: str, *components: Any) -> None:
        self.custom_id = custom_id
        self.title = title
        self.components = list(components)

    def to_dict(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for c in self.components:
            if isinstance(c, (ActionRow, Label)):
                rows.append(c.to_dict())
            else:
                rows.append(ActionRow([c]).to_dict())
        return {"custom_id": self.custom_id, "title": self.title, "components": rows}


# Discord UI Kit (Components v2). flag 32768 is set automatically when these are used


class Container:
    """Components v2 layout block. `accent_color` is an integer color for
    the left-edge bar."""

    is_ui_kit = True

    def __init__(self, components: Iterable[Any], accent_color: int | None = None, spoiler: bool = False) -> None:
        self.components = list(components)
        self.accent_color = accent_color
        self.spoiler = spoiler

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": 17, "components": [c.to_dict() for c in self.components]}
        if self.accent_color is not None:
            d["accent_color"] = self.accent_color
        if self.spoiler:
            d["spoiler"] = True
        return d


class Section:
    """Components v2 layout block. Holds up to 3 `TextDisplay`s with an
    optional `Thumbnail` or `Button` accessory."""

    is_ui_kit = True

    def __init__(self, *components: Any, accessory: Any = None) -> None:
        self.components = list(components)
        self.accessory = accessory

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": 9, "components": [c.to_dict() for c in self.components]}
        if self.accessory is not None:
            d["accessory"] = self.accessory.to_dict() if hasattr(self.accessory, "to_dict") else self.accessory
        return d


class TextDisplay:
    """Components v2 layout block: a block of markdown text."""

    is_ui_kit = True

    def __init__(self, content: str) -> None:
        self.content = content

    def to_dict(self) -> dict[str, Any]:
        return {"type": 10, "content": self.content}


class Thumbnail:
    """Components v2 layout block: a small image, typically used as a
    `Section`'s accessory."""

    is_ui_kit = True

    def __init__(self, url: str, description: str | None = None, spoiler: bool = False) -> None:
        self.url = url
        self.description = description
        self.spoiler = spoiler

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": 11, "media": {"url": self.url}}
        if self.description is not None:
            d["description"] = self.description
        if self.spoiler:
            d["spoiler"] = True
        return d


class File:
    """Components v2 layout block: a file attached to this message. `url`
    must be an `"attachment://filename"` reference, matching a file
    uploaded alongside this message."""

    is_ui_kit = True

    def __init__(self, url: str, spoiler: bool = False) -> None:
        self.url = url
        self.spoiler = spoiler

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": 13, "file": {"url": self.url}}
        if self.spoiler:
            d["spoiler"] = True
        return d


class MediaGallery:
    """Components v2 layout block: a gallery of images/videos. `items` are
    dicts, e.g. `{"media": {"url": "..."}}`."""

    is_ui_kit = True

    def __init__(self, *items: Any) -> None:
        self.items = list(items)

    def to_dict(self) -> dict[str, Any]:
        return {"type": 12, "items": self.items}


class Separator:
    """Components v2 layout block: visual spacing between other blocks.
    `spacing` is `1` (small) or `2` (large)."""

    is_ui_kit = True

    def __init__(self, divider: bool = True, spacing: int = 1) -> None:
        self.divider = divider
        self.spacing = spacing

    def to_dict(self) -> dict[str, Any]:
        return {"type": 14, "divider": self.divider, "spacing": self.spacing}
