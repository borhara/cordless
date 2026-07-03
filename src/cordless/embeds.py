"""Discord embed builder."""


class EmbedField:
    def __init__(self, name, value, inline=False):
        self.name = name
        self.value = value
        self.inline = inline

    def to_dict(self):
        d = {"name": self.name, "value": self.value}
        if self.inline:
            d["inline"] = True
        return d


class Embed:
    def __init__(self, title=None, description=None, color=None, url=None, timestamp=None):
        self.title = title
        self.description = description
        self.color = color
        self.url = url
        self.timestamp = timestamp
        self._footer = None
        self._image = None
        self._thumbnail = None
        self._author = None
        self._fields = []

    def set_footer(self, text, icon_url=None):
        self._footer = {"text": text}
        if icon_url is not None:
            self._footer["icon_url"] = icon_url
        return self

    def set_image(self, url):
        self._image = {"url": url}
        return self

    def set_thumbnail(self, url):
        self._thumbnail = {"url": url}
        return self

    def set_author(self, name, url=None, icon_url=None):
        self._author = {"name": name}
        if url is not None:
            self._author["url"] = url
        if icon_url is not None:
            self._author["icon_url"] = icon_url
        return self

    def add_field(self, name, value, inline=False):
        self._fields.append(EmbedField(name, value, inline))
        return self

    def to_dict(self):
        d = {}
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
            d["timestamp"] = ts.isoformat() if hasattr(ts, "isoformat") else ts
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
