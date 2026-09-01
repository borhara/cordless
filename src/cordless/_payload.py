# pyright: strict
"""Message payload helpers shared by the interaction path (context.py), the
REST layer (_rest/) and webhook execution (webhook.py).

A leaf module: it depends only on errors, so importing it never drags in
models.py or the resource layer.
"""

from typing import Any, cast

from .errors import MessageTooLongError

__all__ = [
    "_FLAG_EPHEMERAL",
    "_FLAG_UI_KIT",
    "_attach_files",
    "_contains_uikit",
    "_validate_content_length",
    "_validate_uikit",
    "_with_guild_id",
]

_FLAG_EPHEMERAL = 64
_FLAG_UI_KIT = 32768

_MAX_CONTENT_LENGTH = 2000
_MAX_UIKIT_COMPONENTS = 40
_MAX_UIKIT_TEXT_LENGTH = 4000

# Components v2 types: Section, TextDisplay, Thumbnail, MediaGallery, File, Separator, Container
_UI_KIT_TYPES = {9, 10, 11, 12, 13, 14, 17}


def _contains_uikit(components: Any) -> bool:
    if not components:
        return False
    for c in components:
        if getattr(c, "is_ui_kit", False):
            return True
        if isinstance(c, dict):
            c = cast("dict[str, Any]", c)
            if c.get("type") in _UI_KIT_TYPES:
                return True
            if _contains_uikit(c.get("components")):
                return True
        # recurse into ActionRow children
        elif hasattr(c, "components"):
            if _contains_uikit(c.components):
                return True
    return False


def _count_components(components: Any) -> int:
    """Every component in the tree counts toward the 40 cap, including ones
    nested in a Container/Section/ActionRow and a Section's accessory."""
    if not components:
        return 0
    total = 0
    for c in components:
        total += 1
        if isinstance(c, dict):
            c = cast("dict[str, Any]", c)
            total += _count_components(c.get("components"))
            if c.get("accessory") is not None:
                total += 1
        else:
            if hasattr(c, "components"):
                total += _count_components(c.components)
            if getattr(c, "accessory", None) is not None:
                total += 1
    return total


def _uikit_text_length(components: Any) -> int:
    """Total characters across every TextDisplay, which Discord caps at 4000
    for the whole message."""
    if not components:
        return 0
    total = 0
    for c in components:
        if isinstance(c, dict):
            c = cast("dict[str, Any]", c)
            if c.get("type") == 10:
                total += len(c.get("content") or "")
            total += _uikit_text_length(c.get("components"))
        else:
            if hasattr(c, "content") and not hasattr(c, "components"):
                total += len(c.content or "")
            if hasattr(c, "components"):
                total += _uikit_text_length(c.components)
    return total


def _validate_content_length(content: str | None) -> None:
    """Discord rejects an over-length message on its own end, after we have
    already returned 200 to API Gateway, so check it up front."""
    if content is not None and len(content) > _MAX_CONTENT_LENGTH:
        raise MessageTooLongError(
            f"Message content is {len(content)} characters, which exceeds "
            f"Discord's {_MAX_CONTENT_LENGTH}-character limit"
        )


def _validate_uikit(content: str | None, embeds: Any, components: Any) -> None:
    """Reject a Components v2 message that also sets content or embeds, or
    that busts the component-count/text-length caps, before it is sent.
    Shared by the interaction path and the REST layer's create/edit message
    so both fail the same way. content/embeds must already be None when unset
    (the REST layer normalises its UNSET sentinel first), since None here
    means "no conflict"."""
    if content is not None or embeds is not None:
        raise ValueError("Components v2 messages can't also set content or embeds, use TextDisplay/Container instead")
    count = _count_components(components)
    if count > _MAX_UIKIT_COMPONENTS:
        raise ValueError(
            f"Message has {count} components, which exceeds Discord's {_MAX_UIKIT_COMPONENTS}-component limit"
        )
    text_length = _uikit_text_length(components)
    if text_length > _MAX_UIKIT_TEXT_LENGTH:
        raise MessageTooLongError(
            f"Components v2 text totals {text_length} characters, which exceeds "
            f"Discord's {_MAX_UIKIT_TEXT_LENGTH}-character limit"
        )


def _attach_files(data: dict[str, Any], files: list[tuple[str, bytes]]) -> None:
    """Add the attachments metadata array Discord expects alongside a multipart body.

    Appended after whatever is already in data["attachments"] (e.g. an edit's
    retained-attachment list): the new entries' "id" is the file's index,
    matching the "files[n]" part build_multipart_body gives it, while retained
    attachments keep their real snowflake id.
    """
    existing: list[Any] = data.get("attachments") or []
    data["attachments"] = existing + [{"id": i, "filename": name} for i, (name, _) in enumerate(files)]


def _with_guild_id(data: dict[str, Any] | None, guild_id: str | None) -> dict[str, Any] | None:
    """Discord's member and role payloads carry no guild_id of their own; it
    is implied by the endpoint. Stitch it in so member.add_role()/role.edit()
    and friends know which guild to act on."""
    if data is None or guild_id is None:
        return data
    return {**data, "guild_id": guild_id}
