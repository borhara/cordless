"""Discord UI component builders."""


class _ButtonStyle:
    PRIMARY = 1
    SECONDARY = 2
    SUCCESS = 3
    DANGER = 4
    LINK = 5
    PREMIUM = 6


ButtonStyle = _ButtonStyle()


class SelectOption:
    def __init__(self, label, value, description=None, emoji=None, default=False):
        self.label = label
        self.value = value
        self.description = description
        self.emoji = emoji
        self.default = default

    def to_dict(self):
        d = {"label": self.label, "value": self.value}
        if self.description is not None:
            d["description"] = self.description
        if self.emoji is not None:
            d["emoji"] = self.emoji
        if self.default:
            d["default"] = True
        return d


class Button:
    def __init__(self, label=None, custom_id=None, style=1, url=None, emoji=None, disabled=False, sku_id=None):
        self.label = label
        self.custom_id = custom_id
        self.style = style
        self.url = url
        self.emoji = emoji
        self.disabled = disabled
        self.sku_id = sku_id  # required for style=6 (PREMIUM) buttons

    def to_dict(self):
        d = {"type": 2, "style": self.style}
        # premium buttons (style 6) only take sku_id, no label/custom_id/url
        if self.style == 6:
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
    def __init__(self, *components):
        self.components = list(components)

    def to_dict(self):
        return {"type": 1, "components": [c.to_dict() for c in self.components]}


class StringSelect:
    def __init__(self, custom_id, options, placeholder=None, min_values=1, max_values=1, disabled=False):
        self.custom_id = custom_id
        self.options = options
        self.placeholder = placeholder
        self.min_values = min_values
        self.max_values = max_values
        self.disabled = disabled

    def to_dict(self):
        d = {
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


class UserSelect:
    def __init__(self, custom_id, placeholder=None, min_values=1, max_values=1, disabled=False):
        self.custom_id = custom_id
        self.placeholder = placeholder
        self.min_values = min_values
        self.max_values = max_values
        self.disabled = disabled

    def to_dict(self):
        d = {"type": 5, "custom_id": self.custom_id, "min_values": self.min_values, "max_values": self.max_values}
        if self.placeholder is not None:
            d["placeholder"] = self.placeholder
        if self.disabled:
            d["disabled"] = True
        return d


class RoleSelect:
    def __init__(self, custom_id, placeholder=None, min_values=1, max_values=1, disabled=False):
        self.custom_id = custom_id
        self.placeholder = placeholder
        self.min_values = min_values
        self.max_values = max_values
        self.disabled = disabled

    def to_dict(self):
        d = {"type": 6, "custom_id": self.custom_id, "min_values": self.min_values, "max_values": self.max_values}
        if self.placeholder is not None:
            d["placeholder"] = self.placeholder
        if self.disabled:
            d["disabled"] = True
        return d


class MentionableSelect:
    def __init__(self, custom_id, placeholder=None, min_values=1, max_values=1, disabled=False):
        self.custom_id = custom_id
        self.placeholder = placeholder
        self.min_values = min_values
        self.max_values = max_values
        self.disabled = disabled

    def to_dict(self):
        d = {"type": 7, "custom_id": self.custom_id, "min_values": self.min_values, "max_values": self.max_values}
        if self.placeholder is not None:
            d["placeholder"] = self.placeholder
        if self.disabled:
            d["disabled"] = True
        return d


class ChannelSelect:
    def __init__(self, custom_id, channel_types=None, placeholder=None, min_values=1, max_values=1, disabled=False):
        self.custom_id = custom_id
        self.channel_types = channel_types
        self.placeholder = placeholder
        self.min_values = min_values
        self.max_values = max_values
        self.disabled = disabled

    def to_dict(self):
        d = {"type": 8, "custom_id": self.custom_id, "min_values": self.min_values, "max_values": self.max_values}
        if self.channel_types is not None:
            d["channel_types"] = self.channel_types
        if self.placeholder is not None:
            d["placeholder"] = self.placeholder
        if self.disabled:
            d["disabled"] = True
        return d


class _TextInputStyle:
    SHORT = 1
    PARAGRAPH = 2


TextInputStyle = _TextInputStyle()


class TextInput:
    def __init__(self, custom_id, label, style=1, min_length=None, max_length=None,
                 required=True, value=None, placeholder=None):
        self.custom_id = custom_id
        self.label = label
        self.style = style
        self.min_length = min_length
        self.max_length = max_length
        self.required = required
        self.value = value
        self.placeholder = placeholder

    def to_dict(self):
        d = {"type": 4, "custom_id": self.custom_id, "label": self.label, "style": self.style}
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


class Modal:
    def __init__(self, custom_id, title, *components):
        self.custom_id = custom_id
        self.title = title
        self.components = list(components)

    def to_dict(self):
        rows = []
        for c in self.components:
            if isinstance(c, ActionRow):
                rows.append(c.to_dict())
            else:
                rows.append(ActionRow(c).to_dict())
        return {"custom_id": self.custom_id, "title": self.title, "components": rows}


# Discord UI Kit (Components v2). flag 32768 is set automatically when these are used

class Container:
    is_ui_kit = True

    def __init__(self, *components, accent_color=None, spoiler=False):
        self.components = list(components)
        self.accent_color = accent_color
        self.spoiler = spoiler

    def to_dict(self):
        d = {"type": 17, "components": [c.to_dict() for c in self.components]}
        if self.accent_color is not None:
            d["accent_color"] = self.accent_color
        if self.spoiler:
            d["spoiler"] = True
        return d


class Section:
    is_ui_kit = True

    def __init__(self, *components, accessory=None):
        self.components = list(components)
        self.accessory = accessory

    def to_dict(self):
        d = {"type": 9, "components": [c.to_dict() for c in self.components]}
        if self.accessory is not None:
            d["accessory"] = self.accessory.to_dict() if hasattr(self.accessory, "to_dict") else self.accessory
        return d


class TextDisplay:
    is_ui_kit = True

    def __init__(self, content):
        self.content = content

    def to_dict(self):
        return {"type": 10, "content": self.content}


class Thumbnail:
    is_ui_kit = True

    def __init__(self, url, description=None, spoiler=False):
        self.url = url
        self.description = description
        self.spoiler = spoiler

    def to_dict(self):
        d = {"type": 11, "media": {"url": self.url}}
        if self.description is not None:
            d["description"] = self.description
        if self.spoiler:
            d["spoiler"] = True
        return d


class MediaGallery:
    is_ui_kit = True

    def __init__(self, *items):
        self.items = list(items)

    def to_dict(self):
        return {"type": 12, "items": self.items}


class Separator:
    is_ui_kit = True

    def __init__(self, divider=True, spacing=1):
        self.divider = divider
        self.spacing = spacing

    def to_dict(self):
        return {"type": 14, "divider": self.divider, "spacing": self.spacing}
