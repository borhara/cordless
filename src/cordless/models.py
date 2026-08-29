# bit values from Discord's permissions flags docs. new bits get added
# there occasionally, check against the current docs before adding one.
_PERMISSION_BITS = {
    "create_instant_invite": 0x1,
    "kick_members": 0x2,
    "ban_members": 0x4,
    "administrator": 0x8,
    "manage_channels": 0x10,
    "manage_guild": 0x20,
    "add_reactions": 0x40,
    "view_audit_log": 0x80,
    "priority_speaker": 0x100,
    "stream": 0x200,
    "view_channel": 0x400,
    "send_messages": 0x800,
    "send_tts_messages": 0x1000,
    "manage_messages": 0x2000,
    "embed_links": 0x4000,
    "attach_files": 0x8000,
    "read_message_history": 0x10000,
    "mention_everyone": 0x20000,
    "use_external_emojis": 0x40000,
    "view_guild_insights": 0x80000,
    "connect": 0x100000,
    "speak": 0x200000,
    "mute_members": 0x400000,
    "deafen_members": 0x800000,
    "move_members": 0x1000000,
    "use_vad": 0x2000000,
    "change_nickname": 0x4000000,
    "manage_nicknames": 0x8000000,
    "manage_roles": 0x10000000,
    "manage_webhooks": 0x20000000,
    "manage_guild_expressions": 0x40000000,
    "use_application_commands": 0x80000000,
    "request_to_speak": 0x100000000,
    "manage_events": 0x200000000,
    "manage_threads": 0x400000000,
    "create_public_threads": 0x800000000,
    "create_private_threads": 0x1000000000,
    "use_external_stickers": 0x2000000000,
    "send_messages_in_threads": 0x4000000000,
    "use_embedded_activities": 0x8000000000,
    "moderate_members": 0x10000000000,
    "view_creator_monetization_analytics": 0x20000000000,
    "use_soundboard": 0x40000000000,
    "create_guild_expressions": 0x80000000000,
    "create_events": 0x100000000000,
    "use_external_sounds": 0x200000000000,
    "send_voice_messages": 0x400000000000,
    "send_polls": 0x2000000000000,
    "use_external_apps": 0x4000000000000,
}


class Permissions:
    """A Discord permission bitfield. Read one off an incoming member or
    role, e.g. `ctx.member.permissions.manage_guild`, or build one to send,
    e.g. `default_member_permissions=Permissions(manage_guild=True)`.

    `raw` is the starting value (Discord sends this as a string of a big
    int, e.g. off `ctx.member.permissions` or `ctx.role.permissions`).
    Keyword args set or clear individual named bits on top of that, e.g.
    `Permissions(manage_guild=True, kick_members=True)`."""

    def __init__(self, raw=0, **flags):
        self.value = int(raw or 0)
        for name, on in flags.items():
            if name not in _PERMISSION_BITS:
                raise TypeError(f"unknown permission: {name!r}")
            bit = _PERMISSION_BITS[name]
            self.value = (self.value | bit) if on else (self.value & ~bit)

    def __getattr__(self, name):
        try:
            bit = _PERMISSION_BITS[name]
        except KeyError:
            raise AttributeError(name) from None
        return bool(self.value & bit)

    def __int__(self):
        return self.value

    def __repr__(self):
        return f"Permissions({self.value})"


_CDN_BASE = "https://cdn.discordapp.com"


def _cdn_asset_url(path, image_hash):
    """Discord CDN URL for an asset hash. `path` already has the owning
    id baked in (e.g. "avatars/123/{hash}"); hashes prefixed "a_" are
    animated and served as .gif, everything else as .png."""
    if not image_hash:
        return None
    ext = "gif" if image_hash.startswith("a_") else "png"
    return f"{_CDN_BASE}/{path.format(hash=image_hash)}.{ext}"


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

    @property
    def avatar_url(self):
        """Full CDN URL for this user's avatar. Falls back to one of
        Discord's default avatars (indexed off the user id, or the
        discriminator for pre-migration accounts) when no custom avatar
        is set."""
        user_id = self._data.get("id")
        avatar = self._data.get("avatar")
        if avatar and user_id:
            return _cdn_asset_url(f"avatars/{user_id}/{{hash}}", avatar)
        if not user_id:
            return None
        discriminator = self._data.get("discriminator")
        index = int(discriminator) % 5 if discriminator and discriminator != "0" else (int(user_id) >> 22) % 6
        return f"{_CDN_BASE}/embed/avatars/{index}.png"

    @property
    def banner_url(self):
        """Full CDN URL for this user's profile banner, or `None` if
        they don't have one set."""
        user_id = self._data.get("id")
        banner = self._data.get("banner")
        return _cdn_asset_url(f"banners/{user_id}/{{hash}}", banner) if user_id else None

    async def fetch(self, **kwargs):
        """Re-fetch this user by id. Returns a fresh `User`. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import users

        return await users.fetch_user(self.id, **kwargs)

    async def create_dm(self, **kwargs):
        """Open (or fetch the existing) DM channel with this user. Returns
        the DM `Channel`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import users

        return await users.create_dm(self.id, **kwargs)


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

    @property
    def permissions(self):
        """This member's permissions, as a `Permissions` object
        (`.administrator`, `.manage_guild`, ...) instead of the raw
        bitfield string Discord sends."""
        raw = self._data.get("permissions")
        return Permissions(raw) if raw is not None else None

    async def edit(self, **kwargs):
        """Update this member's nick, roles, mute/deaf, voice channel or
        timeout. Returns the updated `Member`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import members

        return await members.edit_guild_member(self._data["guild_id"], self._data["user"]["id"], **kwargs)

    async def add_role(self, role_id, **kwargs):
        """Grant this member a role. Requires `DISCORD_BOT_TOKEN` and `MANAGE_ROLES`."""
        from ._rest import members

        await members.add_guild_member_role(self._data["guild_id"], self._data["user"]["id"], role_id, **kwargs)

    async def remove_role(self, role_id, **kwargs):
        """Remove a role from this member. Requires `DISCORD_BOT_TOKEN` and `MANAGE_ROLES`."""
        from ._rest import members

        await members.remove_guild_member_role(self._data["guild_id"], self._data["user"]["id"], role_id, **kwargs)

    async def kick(self, **kwargs):
        """Remove this member from the guild. Requires `DISCORD_BOT_TOKEN`
        and `KICK_MEMBERS`."""
        from ._rest import members

        await members.remove_guild_member(self._data["guild_id"], self._data["user"]["id"], **kwargs)

    async def timeout(self, until, **kwargs):
        """Time this member out until an ISO 8601 timestamp (up to 28 days
        out), or pass `None` to clear an existing timeout. Requires
        `DISCORD_BOT_TOKEN` and `MODERATE_MEMBERS`."""
        from ._rest import members

        return await members.edit_guild_member(
            self._data["guild_id"], self._data["user"]["id"], communication_disabled_until=until, **kwargs
        )


class Message(DiscordObject):
    """A Discord message, e.g. `ctx.message` (the message a component sits
    on). `.id`, `.content`, `.embeds`, and any other field Discord sends are
    available as attributes."""

    @property
    def author(self):
        """The message's sender, as a `User`."""
        author_data = self._data.get("author")
        return User(author_data) if author_data is not None else None

    async def pin(self, **kwargs):
        """Pin this message in its channel. Requires `DISCORD_BOT_TOKEN` and `PIN_MESSAGES`."""
        from ._rest import channels

        await channels.pin_message(self._data["channel_id"], self.id, **kwargs)

    async def unpin(self, **kwargs):
        """Unpin this message. Requires `DISCORD_BOT_TOKEN` and `PIN_MESSAGES`."""
        from ._rest import channels

        await channels.unpin_message(self._data["channel_id"], self.id, **kwargs)

    async def fetch(self, **kwargs):
        """Re-fetch this message's full object from Discord. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        return await messages.fetch_message(self._data["channel_id"], self.id, **kwargs)

    async def edit(self, **kwargs):
        """Edit this message (only the original author can change
        content/embeds/components; anyone with `MANAGE_MESSAGES` can change
        `flags`). Nullable fields can be cleared by passing `None`. Returns
        the updated `Message`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        return await messages.edit_channel_message(self._data["channel_id"], self.id, **kwargs)

    async def delete(self, **kwargs):
        """Delete this message. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        await messages.delete_channel_message(self._data["channel_id"], self.id, **kwargs)

    async def crosspost(self, **kwargs):
        """Publish this message from an announcement channel to its
        following channels. Returns the updated `Message`. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        return await messages.crosspost_message(self._data["channel_id"], self.id, **kwargs)

    async def reply(self, **kwargs):
        """Send a new message that replies to this one. Same fields as
        `channel.send()`. Returns the sent `Message`. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        reference = {"message_id": self.id}
        return await messages.create_message(self._data["channel_id"], message_reference=reference, **kwargs)

    async def add_reaction(self, emoji, **kwargs):
        """React to this message as the bot. `emoji` is a unicode emoji, or
        `name:id` for a custom one. Requires `DISCORD_BOT_TOKEN` and (unless
        someone already reacted with it) `ADD_REACTIONS`."""
        from ._rest import messages

        await messages.create_reaction(self._data["channel_id"], self.id, emoji, **kwargs)

    async def remove_reaction(self, emoji, user_id=None, **kwargs):
        """Remove a reaction. Removes the bot's own by default; pass
        `user_id` to remove someone else's, which needs `MANAGE_MESSAGES`.
        Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        if user_id is None:
            await messages.delete_own_reaction(self._data["channel_id"], self.id, emoji, **kwargs)
        else:
            await messages.delete_user_reaction(self._data["channel_id"], self.id, emoji, user_id, **kwargs)

    async def fetch_reactions(self, emoji, **kwargs):
        """List the users who reacted with a given emoji, as a list of
        `User`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        return await messages.fetch_reactions(self._data["channel_id"], self.id, emoji, **kwargs)

    async def clear_reactions(self, emoji=None, **kwargs):
        """Remove every reaction from this message, or every reaction for
        one emoji if `emoji` is given. Requires `DISCORD_BOT_TOKEN` and
        `MANAGE_MESSAGES`."""
        from ._rest import messages

        if emoji is None:
            await messages.delete_all_reactions(self._data["channel_id"], self.id, **kwargs)
        else:
            await messages.delete_all_reactions_for_emoji(self._data["channel_id"], self.id, emoji, **kwargs)

    async def fetch_poll_answer_voters(self, answer_id, **kwargs):
        """List the users who voted for one answer on this message's poll,
        as a list of `User`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        return await messages.fetch_poll_answer_voters(self._data["channel_id"], self.id, answer_id, **kwargs)

    async def expire_poll(self, **kwargs):
        """End this message's poll now, instead of waiting for its normal
        expiry. Returns the updated `Message`. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        return await messages.expire_poll(self._data["channel_id"], self.id, **kwargs)


class Channel(DiscordObject):
    """A partial Discord channel, e.g. `ctx.channel`. `.id`, `.name`,
    `.type`, and any other field Discord sends are available as
    attributes."""

    @property
    def mention(self):
        """`<#id>`, Discord's mention syntax for this channel."""
        return f"<#{self._data['id']}>"

    async def start_thread_from_message(self, message_id, name, **kwargs):
        """Start a thread off an existing message in this channel. Returns
        a `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.start_thread_from_message(self.id, message_id, name, **kwargs)

    async def start_thread_without_message(self, name, **kwargs):
        """Start a thread not attached to any message in this channel.
        Returns a `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.start_thread_without_message(self.id, name, **kwargs)

    async def start_thread_from_forum(self, name, *, message, **kwargs):
        """Start a forum post (a thread with its first message) in this
        forum channel. Returns a `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.start_thread_from_forum(self.id, name, message=message, **kwargs)

    async def fetch_public_archived_threads(self, **kwargs):
        """List this channel's public archived threads, as a list of
        `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.fetch_public_archived_threads(self.id, **kwargs)

    async def fetch_private_archived_threads(self, **kwargs):
        """List this channel's private archived threads, as a list of
        `Thread`. Requires `DISCORD_BOT_TOKEN` and `MANAGE_THREADS`."""
        from ._rest import threads

        return await threads.fetch_private_archived_threads(self.id, **kwargs)

    async def fetch_joined_private_archived_threads(self, **kwargs):
        """List this channel's private archived threads the bot has joined,
        as a list of `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.fetch_joined_private_archived_threads(self.id, **kwargs)

    async def fetch(self, **kwargs):
        """Re-fetch this channel's full object from Discord - `ctx.channel`
        only carries a partial payload. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        return await channels.fetch_channel(self.id, **kwargs)

    async def edit(self, **kwargs):
        """Update this channel's settings. See `_rest.channels.edit_channel`
        for the full field list. Returns the updated `Channel`. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        return await channels.edit_channel(self.id, **kwargs)

    async def delete(self, **kwargs):
        """Delete this channel, close this DM, or delete this thread.
        Returns the now-deleted `Channel`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        return await channels.delete_channel(self.id, **kwargs)

    async def set_permissions(self, overwrite_id, *, type, **kwargs):
        """Add or edit a permission overwrite for a role or member.
        `type` is 0 for a role, 1 for a member. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        await channels.edit_channel_permissions(self.id, overwrite_id, type=type, **kwargs)

    async def delete_permission(self, overwrite_id, **kwargs):
        """Remove a permission overwrite. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        await channels.delete_channel_permission(self.id, overwrite_id, **kwargs)

    async def fetch_invites(self, **kwargs):
        """List this channel's invites, as a list of `Invite`. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        return await channels.fetch_channel_invites(self.id, **kwargs)

    async def create_invite(self, **kwargs):
        """Create an invite to this channel. Returns an `Invite`. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        return await channels.create_channel_invite(self.id, **kwargs)

    async def follow_announcement(self, webhook_channel_id, **kwargs):
        """Mirror this announcement channel's posts into webhook_channel_id.
        Returns a `FollowedChannel`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        return await channels.follow_announcement_channel(self.id, webhook_channel_id, **kwargs)

    async def trigger_typing(self, **kwargs):
        """Show the typing indicator in this channel for ~10 seconds, or
        until a message is sent. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        await channels.trigger_typing(self.id, **kwargs)

    async def set_voice_status(self, status=None, **kwargs):
        """Set (or, with `status=None`, clear) this voice channel's status.
        Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        await channels.set_voice_channel_status(self.id, status, **kwargs)

    async def add_recipient(self, user_id, access_token, **kwargs):
        """Add a user to this group DM, given an OAuth2 token with the
        `gdm.join` scope. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        await channels.add_group_dm_recipient(self.id, user_id, access_token, **kwargs)

    async def remove_recipient(self, user_id, **kwargs):
        """Remove a user from this group DM. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        await channels.remove_group_dm_recipient(self.id, user_id, **kwargs)

    async def fetch_pins(self, **kwargs):
        """List this channel's pinned messages, as a list of `MessagePin`.
        Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        return await channels.fetch_channel_pins(self.id, **kwargs)

    async def pin_message(self, message_id, **kwargs):
        """Pin a message in this channel. Requires `DISCORD_BOT_TOKEN` and `PIN_MESSAGES`."""
        from ._rest import channels

        await channels.pin_message(self.id, message_id, **kwargs)

    async def unpin_message(self, message_id, **kwargs):
        """Unpin a message in this channel. Requires `DISCORD_BOT_TOKEN` and `PIN_MESSAGES`."""
        from ._rest import channels

        await channels.unpin_message(self.id, message_id, **kwargs)

    async def fetch_messages(self, **kwargs):
        """List recent messages in this channel, newest first, as a list
        of `Message`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        return await messages.fetch_channel_messages(self.id, **kwargs)

    async def fetch_message(self, message_id, **kwargs):
        """Fetch a single `Message` by id. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        return await messages.fetch_message(self.id, message_id, **kwargs)

    async def send(self, **kwargs):
        """Send a message with the full Create Message field set (replies
        via `message_reference`, `poll`, `sticker_ids`, `tts`, `nonce`, ...),
        unlike the simpler `bot.send_message()`. Returns the sent `Message`.
        Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import messages

        return await messages.create_message(self.id, **kwargs)

    async def bulk_delete_messages(self, message_ids, **kwargs):
        """Delete 2-100 messages at once, none older than two weeks.
        Guild channels only. Requires `DISCORD_BOT_TOKEN` and `MANAGE_MESSAGES`."""
        from ._rest import messages

        await messages.bulk_delete_messages(self.id, message_ids, **kwargs)

    async def fetch_webhooks(self, **kwargs):
        """List this channel's webhooks, as a list of `Webhook`. Requires
        `DISCORD_BOT_TOKEN` and `MANAGE_WEBHOOKS`."""
        from ._rest import webhooks

        return await webhooks.fetch_channel_webhooks(self.id, **kwargs)

    async def create_stage_instance(self, topic, **kwargs):
        """Start a live Stage on this Stage channel. Returns the new
        `StageInstance`. Requires `DISCORD_BOT_TOKEN` and Stage moderator
        permissions."""
        from ._rest import stage_instances

        return await stage_instances.create_stage_instance(self.id, topic, **kwargs)

    async def fetch_stage_instance(self, **kwargs):
        """Fetch this Stage channel's live `StageInstance`, if it has one.
        Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import stage_instances

        return await stage_instances.fetch_stage_instance(self.id, **kwargs)

    async def send_soundboard_sound(self, sound_id, **kwargs):
        """Play a soundboard sound in this channel's voice channel. Bot
        must already be connected to it. Requires `DISCORD_BOT_TOKEN`,
        `SPEAK` and `USE_SOUNDBOARD`."""
        from ._rest import soundboard

        await soundboard.send_soundboard_sound(self.id, sound_id, **kwargs)


class Attachment(DiscordObject):
    """A file attached to a command's `attachment` option, e.g.
    `ctx.attachments[att_id]`. `.id`, `.filename`, `.url`, `.size`,
    `.content_type`, and any other field Discord sends are available as
    attributes."""


class Role(DiscordObject):
    """A Discord role, e.g. `ctx.resolved_roles[role_id]` from a `RoleSelect`
    or `MentionableSelect` pick. `.id`, `.name`, `.color`, `.permissions`,
    and any other field Discord sends are available as attributes."""

    @property
    def mention(self):
        """`<@&id>`, Discord's mention syntax for this role."""
        return f"<@&{self._data['id']}>"

    @property
    def icon_url(self):
        """Full CDN URL for this role's custom icon, or `None` if it
        doesn't have one (roles that use an emoji instead of an
        uploaded icon don't have one)."""
        role_id = self._data.get("id")
        icon = self._data.get("icon")
        return _cdn_asset_url(f"role-icons/{role_id}/{{hash}}", icon) if role_id else None

    @property
    def permissions(self):
        """This role's permissions, as a `Permissions` object
        (`.administrator`, `.manage_guild`, ...) instead of the raw
        bitfield string Discord sends."""
        raw = self._data.get("permissions")
        return Permissions(raw) if raw is not None else None

    async def edit(self, **kwargs):
        """Update this role. Returns the updated `Role`. Requires
        `DISCORD_BOT_TOKEN` and `MANAGE_ROLES`."""
        from ._rest import members

        return await members.edit_guild_role(self._data["guild_id"], self.id, **kwargs)

    async def delete(self, **kwargs):
        """Delete this role. Requires `DISCORD_BOT_TOKEN` and `MANAGE_ROLES`."""
        from ._rest import members

        await members.delete_guild_role(self._data["guild_id"], self.id, **kwargs)


class Guild(DiscordObject):
    """A Discord guild, e.g. `ctx.guild`. Built from the partial guild object
    Discord includes on the interaction, so most fields beyond `.id`,
    `.locale`, and `.features` are not present here."""

    @property
    def icon_url(self):
        """Full CDN URL for this guild's icon, or `None` if unset."""
        guild_id = self._data.get("id")
        icon = self._data.get("icon")
        return _cdn_asset_url(f"icons/{guild_id}/{{hash}}", icon) if guild_id else None

    @property
    def banner_url(self):
        """Full CDN URL for this guild's banner, or `None` if unset."""
        guild_id = self._data.get("id")
        banner = self._data.get("banner")
        return _cdn_asset_url(f"banners/{guild_id}/{{hash}}", banner) if guild_id else None

    @property
    def splash_url(self):
        """Full CDN URL for this guild's invite splash, or `None` if unset."""
        guild_id = self._data.get("id")
        splash = self._data.get("splash")
        return _cdn_asset_url(f"splashes/{guild_id}/{{hash}}", splash) if guild_id else None

    @property
    def discovery_splash_url(self):
        """Full CDN URL for this guild's discovery splash, or `None` if
        unset."""
        guild_id = self._data.get("id")
        splash = self._data.get("discovery_splash")
        return _cdn_asset_url(f"discovery-splashes/{guild_id}/{{hash}}", splash) if guild_id else None

    def widget_image_url(self, style="shield"):
        """Full URL for this guild's widget image (a live PNG showing member
        count). Public and unauthenticated, so this just builds the URL, it
        doesn't call Discord. `style` is one of "shield", "banner1",
        "banner2", "banner3", "banner4"."""
        return f"https://discord.com/api/guilds/{self._data['id']}/widget.png?style={style}"

    async def fetch_active_threads(self, **kwargs):
        """List every active thread in this guild (public and private), as
        a list of `Thread`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import threads

        return await threads.fetch_active_guild_threads(self.id, **kwargs)

    async def create_channel(self, name, **kwargs):
        """Create a channel in this guild. `type` picks the kind (0 text,
        2 voice, 4 category, 5 announcement, 13 stage, 15 forum, 16 media,
        ...); see `_rest.channels.create_guild_channel` for the full field
        list. Returns the new `Channel`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        return await channels.create_guild_channel(self.id, name, **kwargs)

    async def fetch_channels(self, **kwargs):
        """List this guild's channels, as a list of `Channel`. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        return await channels.fetch_guild_channels(self.id, **kwargs)

    async def edit_channel_positions(self, positions, **kwargs):
        """Reorder this guild's channels. `positions` is a list of
        `{"id": channel_id, "position": int, ...}` dicts. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import channels

        await channels.edit_guild_channel_positions(self.id, positions, **kwargs)

    async def fetch(self, **kwargs):
        """Re-fetch this guild's full object from Discord - `ctx.guild`
        only carries `.id`, `.locale`, `.features`. Pass `with_counts=True`
        for approximate member/presence counts. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import guilds

        return await guilds.fetch_guild(self.id, **kwargs)

    async def fetch_preview(self, **kwargs):
        """Fetch this guild's preview object. Requires `DISCORD_BOT_TOKEN`
        unless the guild is discoverable."""
        from ._rest import guilds

        return await guilds.fetch_guild_preview(self.id, **kwargs)

    async def edit(self, **kwargs):
        """Update this guild's settings. See `_rest.guilds.edit_guild` for
        the full field list. Returns the updated `Guild`. Requires
        `DISCORD_BOT_TOKEN` and `MANAGE_GUILD`."""
        from ._rest import guilds

        return await guilds.edit_guild(self.id, **kwargs)

    async def delete(self, **kwargs):
        """Delete this guild. Bot must be the guild's owner. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import guilds

        await guilds.delete_guild(self.id, **kwargs)

    async def fetch_bans(self, **kwargs):
        """List this guild's bans, as a list of `Ban`. Requires
        `DISCORD_BOT_TOKEN` and `BAN_MEMBERS`."""
        from ._rest import guilds

        return await guilds.fetch_guild_bans(self.id, **kwargs)

    async def fetch_ban(self, user_id, **kwargs):
        """Fetch a single `Ban` by user id. Requires `DISCORD_BOT_TOKEN`
        and `BAN_MEMBERS`."""
        from ._rest import guilds

        return await guilds.fetch_guild_ban(self.id, user_id, **kwargs)

    async def ban(self, user_id, **kwargs):
        """Ban a user, optionally deleting their recent messages via
        `delete_message_seconds`. Requires `DISCORD_BOT_TOKEN` and
        `BAN_MEMBERS`."""
        from ._rest import guilds

        await guilds.create_guild_ban(self.id, user_id, **kwargs)

    async def unban(self, user_id, **kwargs):
        """Remove a ban. Requires `DISCORD_BOT_TOKEN` and `BAN_MEMBERS`."""
        from ._rest import guilds

        await guilds.remove_guild_ban(self.id, user_id, **kwargs)

    async def bulk_ban(self, user_ids, **kwargs):
        """Ban up to 200 users at once. Returns a `BulkBanResult`. Requires
        `DISCORD_BOT_TOKEN`, `BAN_MEMBERS` and `MANAGE_GUILD`."""
        from ._rest import guilds

        return await guilds.bulk_guild_ban(self.id, user_ids, **kwargs)

    async def fetch_prune_count(self, **kwargs):
        """Preview how many inactive members a prune would remove, without
        removing them. Requires `DISCORD_BOT_TOKEN`, `MANAGE_GUILD` and
        `KICK_MEMBERS`."""
        from ._rest import guilds

        return await guilds.fetch_guild_prune_count(self.id, **kwargs)

    async def prune(self, **kwargs):
        """Kick inactive members. Returns the number removed, or `None`
        if `compute_prune_count=False`. Requires `DISCORD_BOT_TOKEN`,
        `MANAGE_GUILD` and `KICK_MEMBERS`."""
        from ._rest import guilds

        return await guilds.begin_guild_prune(self.id, **kwargs)

    async def fetch_voice_regions(self, **kwargs):
        """List this guild's available voice regions, as a list of
        `VoiceRegion`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import guilds

        return await guilds.fetch_guild_voice_regions(self.id, **kwargs)

    async def fetch_voice_state(self, **kwargs):
        """Fetch the bot's own voice state in this guild, as a
        `VoiceState`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import voice

        return await voice.fetch_current_user_voice_state(self.id, **kwargs)

    async def fetch_member_voice_state(self, user_id, **kwargs):
        """Fetch a member's voice state in this guild, as a `VoiceState`.
        Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import voice

        return await voice.fetch_user_voice_state(self.id, user_id, **kwargs)

    async def edit_voice_state(self, **kwargs):
        """Update the bot's own voice state - move it with `channel_id`,
        or request/cancel a Stage speaker request with
        `request_to_speak_timestamp`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import voice

        await voice.edit_current_user_voice_state(self.id, **kwargs)

    async def edit_member_voice_state(self, user_id, **kwargs):
        """Move a member on a Stage channel - `suppress=False` invites them
        to speak, `suppress=True` moves them back to the audience.
        Requires `DISCORD_BOT_TOKEN` and `MUTE_MEMBERS`."""
        from ._rest import voice

        await voice.edit_user_voice_state(self.id, user_id, **kwargs)

    async def fetch_invites(self, **kwargs):
        """List every invite across this guild, as a list of `Invite`.
        Requires `DISCORD_BOT_TOKEN` and `MANAGE_GUILD` or `VIEW_AUDIT_LOG`."""
        from ._rest import guilds

        return await guilds.fetch_guild_invites(self.id, **kwargs)

    async def fetch_integrations(self, **kwargs):
        """List this guild's integrations, as a list of `Integration`.
        Requires `DISCORD_BOT_TOKEN` and `MANAGE_GUILD`."""
        from ._rest import guilds

        return await guilds.fetch_guild_integrations(self.id, **kwargs)

    async def delete_integration(self, integration_id, **kwargs):
        """Delete an integration, its webhooks, and kick its bot if it has
        one. Requires `DISCORD_BOT_TOKEN` and `MANAGE_GUILD`."""
        from ._rest import guilds

        await guilds.delete_guild_integration(self.id, integration_id, **kwargs)

    async def fetch_widget_settings(self, **kwargs):
        """Fetch this guild's widget settings. Requires `DISCORD_BOT_TOKEN`
        and `MANAGE_GUILD`."""
        from ._rest import guilds

        return await guilds.fetch_guild_widget_settings(self.id, **kwargs)

    async def edit_widget(self, **kwargs):
        """Update this guild's widget settings (`enabled`, `channel_id`).
        Requires `DISCORD_BOT_TOKEN` and `MANAGE_GUILD`."""
        from ._rest import guilds

        return await guilds.edit_guild_widget(self.id, **kwargs)

    async def fetch_widget(self, **kwargs):
        """Fetch this guild's public widget object. No token required if
        the widget is enabled."""
        from ._rest import guilds

        return await guilds.fetch_guild_widget(self.id, **kwargs)

    async def fetch_vanity_url(self, **kwargs):
        """Fetch this guild's vanity invite, as a partial `Invite` (`.code`
        is `None` if unset). Requires `DISCORD_BOT_TOKEN` and `MANAGE_GUILD`."""
        from ._rest import guilds

        return await guilds.fetch_guild_vanity_url(self.id, **kwargs)

    async def fetch_welcome_screen(self, **kwargs):
        """Fetch this guild's welcome screen. Requires `DISCORD_BOT_TOKEN`
        and `MANAGE_GUILD` unless the welcome screen is enabled."""
        from ._rest import guilds

        return await guilds.fetch_guild_welcome_screen(self.id, **kwargs)

    async def edit_welcome_screen(self, **kwargs):
        """Update this guild's welcome screen. Requires `DISCORD_BOT_TOKEN`
        and `MANAGE_GUILD`."""
        from ._rest import guilds

        return await guilds.edit_guild_welcome_screen(self.id, **kwargs)

    async def fetch_onboarding(self, **kwargs):
        """Fetch this guild's onboarding configuration. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import guilds

        return await guilds.fetch_guild_onboarding(self.id, **kwargs)

    async def edit_onboarding(self, **kwargs):
        """Update this guild's onboarding configuration. Requires
        `DISCORD_BOT_TOKEN`, `MANAGE_GUILD` and `MANAGE_ROLES`."""
        from ._rest import guilds

        return await guilds.edit_guild_onboarding(self.id, **kwargs)

    async def edit_incident_actions(self, **kwargs):
        """Pause invites and/or DMs for up to 24 hours (raid protection).
        Requires `DISCORD_BOT_TOKEN` and `MANAGE_GUILD`."""
        from ._rest import guilds

        return await guilds.edit_guild_incident_actions(self.id, **kwargs)

    async def fetch_member(self, user_id, **kwargs):
        """Fetch a single guild `Member` by user id. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import members

        return await members.fetch_guild_member(self.id, user_id, **kwargs)

    async def fetch_members(self, **kwargs):
        """List this guild's members, as a list of `Member`. Requires the
        `GUILD_MEMBERS` privileged intent and `DISCORD_BOT_TOKEN`."""
        from ._rest import members

        return await members.fetch_guild_members(self.id, **kwargs)

    async def search_members(self, query, **kwargs):
        """Find members whose username or nickname starts with query, as a
        list of `Member`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import members

        return await members.search_guild_members(self.id, query, **kwargs)

    async def add_member(self, user_id, access_token, **kwargs):
        """Add a user to this guild via an OAuth2 token with the
        `guilds.join` scope. Returns the new `Member`, or `None` if they
        were already a member. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import members

        return await members.add_guild_member(self.id, user_id, access_token, **kwargs)

    async def edit_member(self, user_id, **kwargs):
        """Update a member's nick, roles, mute/deaf, voice channel or
        timeout. Returns the updated `Member`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import members

        return await members.edit_guild_member(self.id, user_id, **kwargs)

    async def edit_current_member(self, **kwargs):
        """Update the bot's own nick, banner, avatar or bio in this guild.
        Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import members

        return await members.edit_current_member(self.id, **kwargs)

    async def add_member_role(self, user_id, role_id, **kwargs):
        """Grant a role to a member. Requires `DISCORD_BOT_TOKEN` and `MANAGE_ROLES`."""
        from ._rest import members

        await members.add_guild_member_role(self.id, user_id, role_id, **kwargs)

    async def remove_member_role(self, user_id, role_id, **kwargs):
        """Remove a role from a member. Requires `DISCORD_BOT_TOKEN` and `MANAGE_ROLES`."""
        from ._rest import members

        await members.remove_guild_member_role(self.id, user_id, role_id, **kwargs)

    async def kick(self, user_id, **kwargs):
        """Remove a member from this guild. Requires `DISCORD_BOT_TOKEN` and
        `KICK_MEMBERS`."""
        from ._rest import members

        await members.remove_guild_member(self.id, user_id, **kwargs)

    async def fetch_roles(self, **kwargs):
        """List this guild's roles, as a list of `Role`. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import members

        return await members.fetch_guild_roles(self.id, **kwargs)

    async def fetch_role(self, role_id, **kwargs):
        """Fetch a single `Role` by id. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import members

        return await members.fetch_guild_role(self.id, role_id, **kwargs)

    async def fetch_role_member_counts(self, **kwargs):
        """Map of role id to member count, excluding @everyone. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import members

        return await members.fetch_guild_role_member_counts(self.id, **kwargs)

    async def create_role(self, **kwargs):
        """Create a role in this guild. Returns the new `Role`. Requires
        `DISCORD_BOT_TOKEN` and `MANAGE_ROLES`."""
        from ._rest import members

        return await members.create_guild_role(self.id, **kwargs)

    async def edit_role_positions(self, positions, **kwargs):
        """Reorder this guild's roles. `positions` is a list of
        `{"id": role_id, "position": int}` dicts. Returns every `Role` in
        the guild. Requires `DISCORD_BOT_TOKEN` and `MANAGE_ROLES`."""
        from ._rest import members

        return await members.edit_guild_role_positions(self.id, positions, **kwargs)

    async def search_messages(self, **kwargs):
        """Full text search across this guild's messages. Returns a
        `MessageSearchResult`. Requires `DISCORD_BOT_TOKEN`,
        `READ_MESSAGE_HISTORY`, and possibly the `MESSAGE_CONTENT`
        privileged intent."""
        from ._rest import messages

        return await messages.search_guild_messages(self.id, **kwargs)

    async def fetch_webhooks(self, **kwargs):
        """List this guild's webhooks, as a list of `Webhook`. Requires
        `DISCORD_BOT_TOKEN` and `MANAGE_WEBHOOKS`."""
        from ._rest import webhooks

        return await webhooks.fetch_guild_webhooks(self.id, **kwargs)

    async def fetch_emojis(self, **kwargs):
        """List this guild's custom emojis, as a list of `Emoji`. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import emojis

        return await emojis.fetch_guild_emojis(self.id, **kwargs)

    async def fetch_emoji(self, emoji_id, **kwargs):
        """Fetch a single custom emoji by id. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import emojis

        return await emojis.fetch_guild_emoji(self.id, emoji_id, **kwargs)

    async def create_emoji(self, name, image, **kwargs):
        """Upload a new custom emoji (128x128, up to 256 KiB). `image` is
        base64 image data. Returns the new `Emoji`. Requires
        `DISCORD_BOT_TOKEN` and `CREATE_GUILD_EXPRESSIONS`."""
        from ._rest import emojis

        return await emojis.create_guild_emoji(self.id, name, image, **kwargs)

    async def fetch_stickers(self, **kwargs):
        """List this guild's stickers, as a list of `Sticker`. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import stickers

        return await stickers.fetch_guild_stickers(self.id, **kwargs)

    async def fetch_sticker(self, sticker_id, **kwargs):
        """Fetch a single guild sticker by id. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import stickers

        return await stickers.fetch_guild_sticker(self.id, sticker_id, **kwargs)

    async def create_sticker(self, name, description, tags, filename, file_bytes, **kwargs):
        """Upload a new sticker (PNG, APNG, GIF, or Lottie JSON, up to 512 KiB,
        320x320, animated ones under 5 seconds). Returns the new `Sticker`.
        Requires `DISCORD_BOT_TOKEN` and `CREATE_GUILD_EXPRESSIONS`."""
        from ._rest import stickers

        return await stickers.create_guild_sticker(self.id, name, description, tags, filename, file_bytes, **kwargs)

    async def fetch_soundboard_sounds(self, **kwargs):
        """List this guild's soundboard sounds, as a list of
        `SoundboardSound`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import soundboard

        return await soundboard.fetch_guild_soundboard_sounds(self.id, **kwargs)

    async def fetch_soundboard_sound(self, sound_id, **kwargs):
        """Fetch a single soundboard sound from this guild. Requires
        `DISCORD_BOT_TOKEN`."""
        from ._rest import soundboard

        return await soundboard.fetch_guild_soundboard_sound(self.id, sound_id, **kwargs)

    async def create_soundboard_sound(self, name, sound, **kwargs):
        """Add a soundboard sound to this guild. `sound` is a base64 data
        URI, same convention as `create_emoji`'s `image`. Returns the new
        `SoundboardSound`. Requires `DISCORD_BOT_TOKEN` and
        `CREATE_GUILD_EXPRESSIONS`/`MANAGE_GUILD_EXPRESSIONS`."""
        from ._rest import soundboard

        return await soundboard.create_guild_soundboard_sound(self.id, name, sound, **kwargs)

    async def fetch_scheduled_events(self, **kwargs):
        """List this guild's scheduled events, as a list of
        `GuildScheduledEvent`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import scheduled_events

        return await scheduled_events.fetch_guild_scheduled_events(self.id, **kwargs)

    async def create_scheduled_event(self, name, privacy_level, scheduled_start_time, entity_type, **kwargs):
        """Create a scheduled event. `entity_type` picks the kind (1 stage,
        2 voice, 3 external); external events also need `channel_id=None`,
        `entity_metadata={"location": ...}` and `scheduled_end_time`. Returns
        the new `GuildScheduledEvent`. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import scheduled_events

        return await scheduled_events.create_guild_scheduled_event(
            self.id, name, privacy_level, scheduled_start_time, entity_type, **kwargs
        )

    async def fetch_scheduled_event(self, event_id, **kwargs):
        """Fetch a single scheduled event by id. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import scheduled_events

        return await scheduled_events.fetch_guild_scheduled_event(self.id, event_id, **kwargs)

    async def fetch_auto_moderation_rules(self, **kwargs):
        """List this guild's auto moderation rules, as a list of
        `AutoModerationRule`. Requires `DISCORD_BOT_TOKEN` and `MANAGE_GUILD`."""
        from ._rest import auto_moderation

        return await auto_moderation.fetch_auto_moderation_rules(self.id, **kwargs)

    async def fetch_auto_moderation_rule(self, rule_id, **kwargs):
        """Fetch a single auto moderation rule by id. Requires
        `DISCORD_BOT_TOKEN` and `MANAGE_GUILD`."""
        from ._rest import auto_moderation

        return await auto_moderation.fetch_auto_moderation_rule(self.id, rule_id, **kwargs)

    async def create_auto_moderation_rule(self, name, event_type, trigger_type, actions, **kwargs):
        """Create an auto moderation rule. Returns the new
        `AutoModerationRule`. Requires `DISCORD_BOT_TOKEN` and `MANAGE_GUILD`."""
        from ._rest import auto_moderation

        return await auto_moderation.create_auto_moderation_rule(
            self.id, name, event_type, trigger_type, actions, **kwargs
        )

    async def fetch_templates(self, **kwargs):
        """List this guild's templates, as a list of `GuildTemplate`.
        Requires `DISCORD_BOT_TOKEN` and `MANAGE_GUILD`."""
        from ._rest import templates

        return await templates.fetch_guild_templates(self.id, **kwargs)

    async def create_template(self, name, **kwargs):
        """Create a template from this guild's current state. Returns the
        new `GuildTemplate`. Requires `DISCORD_BOT_TOKEN` and `MANAGE_GUILD`."""
        from ._rest import templates

        return await templates.create_guild_template(self.id, name, **kwargs)

    async def fetch_audit_log(self, **kwargs):
        """Fetch this guild's audit log, as an `AuditLog`. Requires
        `DISCORD_BOT_TOKEN` and `VIEW_AUDIT_LOG`."""
        from ._rest import audit_log

        return await audit_log.fetch_audit_log(self.id, **kwargs)

    async def leave(self, **kwargs):
        """Leave this guild. Requires `DISCORD_BOT_TOKEN`."""
        from ._rest import users

        await users.leave_guild(self.id, **kwargs)


def _wrap(cls, data):
    return cls(data) if data is not None else None
