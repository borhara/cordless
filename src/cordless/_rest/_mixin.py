"""RESTMixin: the flat bot.<verb>_<resource>() surface.

One mixin, not one per resource - Cordless(RESTMixin) is ordinary single
inheritance. Every method here is a thin delegation to a resource module's
free function; the actual request-building/response-parsing logic lives in
those modules (threads.py, channels.py, ...), grouped by resource, so this
file stays pure boilerplate no matter how many resources it grows to cover.

Every method is async, matching the rest of Cordless's public REST surface
(send_message, execute_webhook, ...): await bot.start_thread_from_message(...).
"""

from . import (
    auto_moderation,
    channels,
    emojis,
    guilds,
    invites,
    members,
    messages,
    scheduled_events,
    stickers,
    threads,
    webhooks,
)


class RESTMixin:
    # -- auto moderation --
    async def fetch_auto_moderation_rules(self, guild_id, **kwargs):
        return await auto_moderation.fetch_auto_moderation_rules(guild_id, **kwargs)

    async def fetch_auto_moderation_rule(self, guild_id, rule_id, **kwargs):
        return await auto_moderation.fetch_auto_moderation_rule(guild_id, rule_id, **kwargs)

    async def create_auto_moderation_rule(self, guild_id, name, event_type, trigger_type, actions, **kwargs):
        return await auto_moderation.create_auto_moderation_rule(
            guild_id, name, event_type, trigger_type, actions, **kwargs
        )

    async def edit_auto_moderation_rule(self, guild_id, rule_id, **kwargs):
        return await auto_moderation.edit_auto_moderation_rule(guild_id, rule_id, **kwargs)

    async def delete_auto_moderation_rule(self, guild_id, rule_id, **kwargs):
        return await auto_moderation.delete_auto_moderation_rule(guild_id, rule_id, **kwargs)

    # -- guild scheduled events --
    async def fetch_guild_scheduled_events(self, guild_id, **kwargs):
        return await scheduled_events.fetch_guild_scheduled_events(guild_id, **kwargs)

    async def create_guild_scheduled_event(
        self, guild_id, name, privacy_level, scheduled_start_time, entity_type, **kwargs
    ):
        return await scheduled_events.create_guild_scheduled_event(
            guild_id, name, privacy_level, scheduled_start_time, entity_type, **kwargs
        )

    async def fetch_guild_scheduled_event(self, guild_id, event_id, **kwargs):
        return await scheduled_events.fetch_guild_scheduled_event(guild_id, event_id, **kwargs)

    async def edit_guild_scheduled_event(self, guild_id, event_id, **kwargs):
        return await scheduled_events.edit_guild_scheduled_event(guild_id, event_id, **kwargs)

    async def delete_guild_scheduled_event(self, guild_id, event_id, **kwargs):
        return await scheduled_events.delete_guild_scheduled_event(guild_id, event_id, **kwargs)

    async def fetch_guild_scheduled_event_users(self, guild_id, event_id, **kwargs):
        return await scheduled_events.fetch_guild_scheduled_event_users(guild_id, event_id, **kwargs)

    # -- emojis --
    async def fetch_guild_emojis(self, guild_id, **kwargs):
        return await emojis.fetch_guild_emojis(guild_id, **kwargs)

    async def fetch_guild_emoji(self, guild_id, emoji_id, **kwargs):
        return await emojis.fetch_guild_emoji(guild_id, emoji_id, **kwargs)

    async def create_guild_emoji(self, guild_id, name, image, **kwargs):
        return await emojis.create_guild_emoji(guild_id, name, image, **kwargs)

    async def edit_guild_emoji(self, guild_id, emoji_id, **kwargs):
        return await emojis.edit_guild_emoji(guild_id, emoji_id, **kwargs)

    async def delete_guild_emoji(self, guild_id, emoji_id, **kwargs):
        return await emojis.delete_guild_emoji(guild_id, emoji_id, **kwargs)

    async def fetch_application_emojis(self, application_id, **kwargs):
        return await emojis.fetch_application_emojis(application_id, **kwargs)

    async def fetch_application_emoji(self, application_id, emoji_id, **kwargs):
        return await emojis.fetch_application_emoji(application_id, emoji_id, **kwargs)

    async def create_application_emoji(self, application_id, name, image, **kwargs):
        return await emojis.create_application_emoji(application_id, name, image, **kwargs)

    async def edit_application_emoji(self, application_id, emoji_id, **kwargs):
        return await emojis.edit_application_emoji(application_id, emoji_id, **kwargs)

    async def delete_application_emoji(self, application_id, emoji_id, **kwargs):
        return await emojis.delete_application_emoji(application_id, emoji_id, **kwargs)

    # -- stickers --
    async def fetch_sticker(self, sticker_id, **kwargs):
        return await stickers.fetch_sticker(sticker_id, **kwargs)

    async def fetch_sticker_packs(self, **kwargs):
        return await stickers.fetch_sticker_packs(**kwargs)

    async def fetch_sticker_pack(self, pack_id, **kwargs):
        return await stickers.fetch_sticker_pack(pack_id, **kwargs)

    async def fetch_guild_stickers(self, guild_id, **kwargs):
        return await stickers.fetch_guild_stickers(guild_id, **kwargs)

    async def fetch_guild_sticker(self, guild_id, sticker_id, **kwargs):
        return await stickers.fetch_guild_sticker(guild_id, sticker_id, **kwargs)

    async def create_guild_sticker(self, guild_id, name, description, tags, filename, file_bytes, **kwargs):
        return await stickers.create_guild_sticker(guild_id, name, description, tags, filename, file_bytes, **kwargs)

    async def edit_guild_sticker(self, guild_id, sticker_id, **kwargs):
        return await stickers.edit_guild_sticker(guild_id, sticker_id, **kwargs)

    async def delete_guild_sticker(self, guild_id, sticker_id, **kwargs):
        return await stickers.delete_guild_sticker(guild_id, sticker_id, **kwargs)

    # -- invites --
    async def fetch_invite(self, code, **kwargs):
        return await invites.fetch_invite(code, **kwargs)

    async def delete_invite(self, code, **kwargs):
        return await invites.delete_invite(code, **kwargs)

    # -- webhooks (bot token) --
    # create_webhook()/get_channel_webhooks()/delete_webhook() already live
    # directly on Cordless (see app.py) and delegate to webhooks.py
    # themselves, same reason messages.py has no bot.create_message().
    async def fetch_channel_webhooks(self, channel_id, **kwargs):
        return await webhooks.fetch_channel_webhooks(channel_id, **kwargs)

    async def fetch_guild_webhooks(self, guild_id, **kwargs):
        return await webhooks.fetch_guild_webhooks(guild_id, **kwargs)

    async def fetch_webhook(self, webhook_id, **kwargs):
        return await webhooks.fetch_webhook(webhook_id, **kwargs)

    async def edit_webhook(self, webhook_id, **kwargs):
        return await webhooks.edit_webhook(webhook_id, **kwargs)

    # -- messages and reactions --
    # no bot.create_message()/edit_message() here on purpose - send_message()
    # and edit_message() already own those verbs directly on Cordless (see
    # app.py) and delegate to messages.py themselves; a second, similarly
    # named flat method would just be confusing. Use channel.send() or
    # message.edit() for the fuller field set.
    async def fetch_channel_messages(self, channel_id, **kwargs):
        return await messages.fetch_channel_messages(channel_id, **kwargs)

    async def fetch_message(self, channel_id, message_id, **kwargs):
        return await messages.fetch_message(channel_id, message_id, **kwargs)

    async def crosspost_message(self, channel_id, message_id, **kwargs):
        return await messages.crosspost_message(channel_id, message_id, **kwargs)

    async def bulk_delete_messages(self, channel_id, message_ids, **kwargs):
        return await messages.bulk_delete_messages(channel_id, message_ids, **kwargs)

    async def create_reaction(self, channel_id, message_id, emoji, **kwargs):
        return await messages.create_reaction(channel_id, message_id, emoji, **kwargs)

    async def delete_own_reaction(self, channel_id, message_id, emoji, **kwargs):
        return await messages.delete_own_reaction(channel_id, message_id, emoji, **kwargs)

    async def delete_user_reaction(self, channel_id, message_id, emoji, user_id, **kwargs):
        return await messages.delete_user_reaction(channel_id, message_id, emoji, user_id, **kwargs)

    async def fetch_reactions(self, channel_id, message_id, emoji, **kwargs):
        return await messages.fetch_reactions(channel_id, message_id, emoji, **kwargs)

    async def delete_all_reactions(self, channel_id, message_id, **kwargs):
        return await messages.delete_all_reactions(channel_id, message_id, **kwargs)

    async def delete_all_reactions_for_emoji(self, channel_id, message_id, emoji, **kwargs):
        return await messages.delete_all_reactions_for_emoji(channel_id, message_id, emoji, **kwargs)

    async def search_guild_messages(self, guild_id, **kwargs):
        return await messages.search_guild_messages(guild_id, **kwargs)

    # -- members and roles --
    async def fetch_guild_member(self, guild_id, user_id, **kwargs):
        return await members.fetch_guild_member(guild_id, user_id, **kwargs)

    async def fetch_guild_members(self, guild_id, **kwargs):
        return await members.fetch_guild_members(guild_id, **kwargs)

    async def search_guild_members(self, guild_id, query, **kwargs):
        return await members.search_guild_members(guild_id, query, **kwargs)

    async def add_guild_member(self, guild_id, user_id, access_token, **kwargs):
        return await members.add_guild_member(guild_id, user_id, access_token, **kwargs)

    async def edit_guild_member(self, guild_id, user_id, **kwargs):
        return await members.edit_guild_member(guild_id, user_id, **kwargs)

    async def edit_current_member(self, guild_id, **kwargs):
        return await members.edit_current_member(guild_id, **kwargs)

    async def add_guild_member_role(self, guild_id, user_id, role_id, **kwargs):
        return await members.add_guild_member_role(guild_id, user_id, role_id, **kwargs)

    async def remove_guild_member_role(self, guild_id, user_id, role_id, **kwargs):
        return await members.remove_guild_member_role(guild_id, user_id, role_id, **kwargs)

    async def remove_guild_member(self, guild_id, user_id, **kwargs):
        return await members.remove_guild_member(guild_id, user_id, **kwargs)

    async def fetch_guild_roles(self, guild_id, **kwargs):
        return await members.fetch_guild_roles(guild_id, **kwargs)

    async def fetch_guild_role(self, guild_id, role_id, **kwargs):
        return await members.fetch_guild_role(guild_id, role_id, **kwargs)

    async def fetch_guild_role_member_counts(self, guild_id, **kwargs):
        return await members.fetch_guild_role_member_counts(guild_id, **kwargs)

    async def create_guild_role(self, guild_id, **kwargs):
        return await members.create_guild_role(guild_id, **kwargs)

    async def edit_guild_role_positions(self, guild_id, positions, **kwargs):
        return await members.edit_guild_role_positions(guild_id, positions, **kwargs)

    async def edit_guild_role(self, guild_id, role_id, **kwargs):
        return await members.edit_guild_role(guild_id, role_id, **kwargs)

    async def delete_guild_role(self, guild_id, role_id, **kwargs):
        return await members.delete_guild_role(guild_id, role_id, **kwargs)

    # -- guilds --
    async def fetch_guild(self, guild_id, **kwargs):
        return await guilds.fetch_guild(guild_id, **kwargs)

    async def fetch_guild_preview(self, guild_id, **kwargs):
        return await guilds.fetch_guild_preview(guild_id, **kwargs)

    async def edit_guild(self, guild_id, **kwargs):
        return await guilds.edit_guild(guild_id, **kwargs)

    async def fetch_guild_bans(self, guild_id, **kwargs):
        return await guilds.fetch_guild_bans(guild_id, **kwargs)

    async def fetch_guild_ban(self, guild_id, user_id, **kwargs):
        return await guilds.fetch_guild_ban(guild_id, user_id, **kwargs)

    async def create_guild_ban(self, guild_id, user_id, **kwargs):
        return await guilds.create_guild_ban(guild_id, user_id, **kwargs)

    async def remove_guild_ban(self, guild_id, user_id, **kwargs):
        return await guilds.remove_guild_ban(guild_id, user_id, **kwargs)

    async def bulk_guild_ban(self, guild_id, user_ids, **kwargs):
        return await guilds.bulk_guild_ban(guild_id, user_ids, **kwargs)

    async def fetch_guild_prune_count(self, guild_id, **kwargs):
        return await guilds.fetch_guild_prune_count(guild_id, **kwargs)

    async def begin_guild_prune(self, guild_id, **kwargs):
        return await guilds.begin_guild_prune(guild_id, **kwargs)

    async def fetch_guild_voice_regions(self, guild_id, **kwargs):
        return await guilds.fetch_guild_voice_regions(guild_id, **kwargs)

    async def fetch_guild_invites(self, guild_id, **kwargs):
        return await guilds.fetch_guild_invites(guild_id, **kwargs)

    async def fetch_guild_integrations(self, guild_id, **kwargs):
        return await guilds.fetch_guild_integrations(guild_id, **kwargs)

    async def delete_guild_integration(self, guild_id, integration_id, **kwargs):
        return await guilds.delete_guild_integration(guild_id, integration_id, **kwargs)

    async def fetch_guild_widget_settings(self, guild_id, **kwargs):
        return await guilds.fetch_guild_widget_settings(guild_id, **kwargs)

    async def edit_guild_widget(self, guild_id, **kwargs):
        return await guilds.edit_guild_widget(guild_id, **kwargs)

    async def fetch_guild_widget(self, guild_id, **kwargs):
        return await guilds.fetch_guild_widget(guild_id, **kwargs)

    async def fetch_guild_vanity_url(self, guild_id, **kwargs):
        return await guilds.fetch_guild_vanity_url(guild_id, **kwargs)

    async def fetch_guild_welcome_screen(self, guild_id, **kwargs):
        return await guilds.fetch_guild_welcome_screen(guild_id, **kwargs)

    async def edit_guild_welcome_screen(self, guild_id, **kwargs):
        return await guilds.edit_guild_welcome_screen(guild_id, **kwargs)

    async def fetch_guild_onboarding(self, guild_id, **kwargs):
        return await guilds.fetch_guild_onboarding(guild_id, **kwargs)

    async def edit_guild_onboarding(self, guild_id, **kwargs):
        return await guilds.edit_guild_onboarding(guild_id, **kwargs)

    async def edit_guild_incident_actions(self, guild_id, **kwargs):
        return await guilds.edit_guild_incident_actions(guild_id, **kwargs)

    # -- channels --
    async def fetch_channel(self, channel_id, **kwargs):
        return await channels.fetch_channel(channel_id, **kwargs)

    async def edit_channel(self, channel_id, **kwargs):
        return await channels.edit_channel(channel_id, **kwargs)

    async def delete_channel(self, channel_id, **kwargs):
        return await channels.delete_channel(channel_id, **kwargs)

    async def edit_channel_permissions(self, channel_id, overwrite_id, **kwargs):
        return await channels.edit_channel_permissions(channel_id, overwrite_id, **kwargs)

    async def delete_channel_permission(self, channel_id, overwrite_id, **kwargs):
        return await channels.delete_channel_permission(channel_id, overwrite_id, **kwargs)

    async def fetch_channel_invites(self, channel_id, **kwargs):
        return await channels.fetch_channel_invites(channel_id, **kwargs)

    async def create_channel_invite(self, channel_id, **kwargs):
        return await channels.create_channel_invite(channel_id, **kwargs)

    async def follow_announcement_channel(self, channel_id, webhook_channel_id, **kwargs):
        return await channels.follow_announcement_channel(channel_id, webhook_channel_id, **kwargs)

    async def trigger_typing(self, channel_id, **kwargs):
        return await channels.trigger_typing(channel_id, **kwargs)

    async def set_voice_channel_status(self, channel_id, status=None, **kwargs):
        return await channels.set_voice_channel_status(channel_id, status, **kwargs)

    async def add_group_dm_recipient(self, channel_id, user_id, access_token, **kwargs):
        return await channels.add_group_dm_recipient(channel_id, user_id, access_token, **kwargs)

    async def remove_group_dm_recipient(self, channel_id, user_id, **kwargs):
        return await channels.remove_group_dm_recipient(channel_id, user_id, **kwargs)

    async def fetch_channel_pins(self, channel_id, **kwargs):
        return await channels.fetch_channel_pins(channel_id, **kwargs)

    async def pin_message(self, channel_id, message_id, **kwargs):
        return await channels.pin_message(channel_id, message_id, **kwargs)

    async def unpin_message(self, channel_id, message_id, **kwargs):
        return await channels.unpin_message(channel_id, message_id, **kwargs)

    async def fetch_guild_channels(self, guild_id, **kwargs):
        return await channels.fetch_guild_channels(guild_id, **kwargs)

    async def create_guild_channel(self, guild_id, name, **kwargs):
        return await channels.create_guild_channel(guild_id, name, **kwargs)

    async def edit_guild_channel_positions(self, guild_id, positions, **kwargs):
        return await channels.edit_guild_channel_positions(guild_id, positions, **kwargs)

    # -- threads --
    async def start_thread_from_message(self, channel_id, message_id, name, **kwargs):
        return await threads.start_thread_from_message(channel_id, message_id, name, **kwargs)

    async def start_thread_without_message(self, channel_id, name, **kwargs):
        return await threads.start_thread_without_message(channel_id, name, **kwargs)

    async def start_thread_from_forum(self, channel_id, name, **kwargs):
        return await threads.start_thread_from_forum(channel_id, name, **kwargs)

    async def join_thread(self, channel_id, **kwargs):
        return await threads.join_thread(channel_id, **kwargs)

    async def leave_thread(self, channel_id, **kwargs):
        return await threads.leave_thread(channel_id, **kwargs)

    async def add_thread_member(self, channel_id, user_id, **kwargs):
        return await threads.add_thread_member(channel_id, user_id, **kwargs)

    async def remove_thread_member(self, channel_id, user_id, **kwargs):
        return await threads.remove_thread_member(channel_id, user_id, **kwargs)

    async def fetch_thread_member(self, channel_id, user_id, **kwargs):
        return await threads.fetch_thread_member(channel_id, user_id, **kwargs)

    async def fetch_thread_members(self, channel_id, **kwargs):
        return await threads.fetch_thread_members(channel_id, **kwargs)

    async def fetch_public_archived_threads(self, channel_id, **kwargs):
        return await threads.fetch_public_archived_threads(channel_id, **kwargs)

    async def fetch_private_archived_threads(self, channel_id, **kwargs):
        return await threads.fetch_private_archived_threads(channel_id, **kwargs)

    async def fetch_joined_private_archived_threads(self, channel_id, **kwargs):
        return await threads.fetch_joined_private_archived_threads(channel_id, **kwargs)

    async def fetch_active_guild_threads(self, guild_id, **kwargs):
        return await threads.fetch_active_guild_threads(guild_id, **kwargs)
