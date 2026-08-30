"""RESTMixin: the flat bot.<verb>_<resource>() surface.

One mixin, not one per resource - Cordless(RESTMixin) is ordinary single
inheritance. Every method here is a thin delegation to a resource module's
free function; the actual request-building/response-parsing logic lives in
those modules (threads.py, channels.py, ...), grouped by resource, so this
file stays pure boilerplate no matter how many resources it grows to cover.

Every method is async, matching the rest of Cordless's public REST surface
(send_message, execute_webhook, ...): await bot.start_thread_from_message(...).

Every method is decorated with functools.wraps(<the delegated function>),
purely so its docstring (and real parameter names, in place of the opaque
**kwargs each method actually takes) show up on the generated API reference
docs; it has no effect on runtime behaviour, since every method's own body
still controls what actually gets called.
"""

import functools

from . import (
    application,
    application_commands,
    audit_log,
    auto_moderation,
    channels,
    emojis,
    entitlements,
    guild_requests,
    guilds,
    invites,
    members,
    messages,
    scheduled_events,
    skus,
    soundboard,
    stage_instances,
    stickers,
    subscriptions,
    templates,
    threads,
    users,
    voice,
    webhooks,
)


class RESTMixin:
    # -- application --
    @functools.wraps(application.fetch_current_application)
    async def fetch_application(self, **kwargs):
        return await application.fetch_current_application(**kwargs)

    @functools.wraps(application.edit_current_application)
    async def edit_application(self, **kwargs):
        return await application.edit_current_application(**kwargs)

    # fetch_application() above is already taken (the bot's own application,
    # matching fetch_current_user()'s bare-name convention) - this one looks
    # up any application by id, so it gets a name of its own.
    @functools.wraps(application.fetch_application)
    async def fetch_application_by_id(self, application_id, **kwargs):
        return await application.fetch_application(application_id, **kwargs)

    @functools.wraps(application.fetch_application_role_connection_metadata)
    async def fetch_application_role_connection_metadata(self, application_id, **kwargs):
        return await application.fetch_application_role_connection_metadata(application_id, **kwargs)

    @functools.wraps(application.edit_application_role_connection_metadata)
    async def edit_application_role_connection_metadata(self, application_id, records, **kwargs):
        return await application.edit_application_role_connection_metadata(application_id, records, **kwargs)

    # -- application commands --
    @functools.wraps(application_commands.fetch_global_commands)
    async def fetch_global_commands(self, application_id, **kwargs):
        return await application_commands.fetch_global_commands(application_id, **kwargs)

    @functools.wraps(application_commands.create_global_command)
    async def create_global_command(self, application_id, name, **kwargs):
        return await application_commands.create_global_command(application_id, name, **kwargs)

    @functools.wraps(application_commands.fetch_global_command)
    async def fetch_global_command(self, application_id, command_id, **kwargs):
        return await application_commands.fetch_global_command(application_id, command_id, **kwargs)

    @functools.wraps(application_commands.edit_global_command)
    async def edit_global_command(self, application_id, command_id, **kwargs):
        return await application_commands.edit_global_command(application_id, command_id, **kwargs)

    @functools.wraps(application_commands.delete_global_command)
    async def delete_global_command(self, application_id, command_id, **kwargs):
        return await application_commands.delete_global_command(application_id, command_id, **kwargs)

    @functools.wraps(application_commands.bulk_overwrite_global_commands)
    async def bulk_overwrite_global_commands(self, application_id, commands, **kwargs):
        return await application_commands.bulk_overwrite_global_commands(application_id, commands, **kwargs)

    @functools.wraps(application_commands.fetch_guild_commands)
    async def fetch_guild_commands(self, application_id, guild_id, **kwargs):
        return await application_commands.fetch_guild_commands(application_id, guild_id, **kwargs)

    @functools.wraps(application_commands.create_guild_command)
    async def create_guild_command(self, application_id, guild_id, name, **kwargs):
        return await application_commands.create_guild_command(application_id, guild_id, name, **kwargs)

    @functools.wraps(application_commands.fetch_guild_command)
    async def fetch_guild_command(self, application_id, guild_id, command_id, **kwargs):
        return await application_commands.fetch_guild_command(application_id, guild_id, command_id, **kwargs)

    @functools.wraps(application_commands.edit_guild_command)
    async def edit_guild_command(self, application_id, guild_id, command_id, **kwargs):
        return await application_commands.edit_guild_command(application_id, guild_id, command_id, **kwargs)

    @functools.wraps(application_commands.delete_guild_command)
    async def delete_guild_command(self, application_id, guild_id, command_id, **kwargs):
        return await application_commands.delete_guild_command(application_id, guild_id, command_id, **kwargs)

    @functools.wraps(application_commands.bulk_overwrite_guild_commands)
    async def bulk_overwrite_guild_commands(self, application_id, guild_id, commands, **kwargs):
        return await application_commands.bulk_overwrite_guild_commands(application_id, guild_id, commands, **kwargs)

    @functools.wraps(application_commands.fetch_guild_command_permissions)
    async def fetch_guild_command_permissions(self, application_id, guild_id, **kwargs):
        return await application_commands.fetch_guild_command_permissions(application_id, guild_id, **kwargs)

    @functools.wraps(application_commands.fetch_command_permissions)
    async def fetch_command_permissions(self, application_id, guild_id, command_id, **kwargs):
        return await application_commands.fetch_command_permissions(application_id, guild_id, command_id, **kwargs)

    # -- entitlements and skus --
    @functools.wraps(entitlements.fetch_entitlements)
    async def fetch_entitlements(self, application_id, **kwargs):
        return await entitlements.fetch_entitlements(application_id, **kwargs)

    @functools.wraps(entitlements.fetch_entitlement)
    async def fetch_entitlement(self, application_id, entitlement_id, **kwargs):
        return await entitlements.fetch_entitlement(application_id, entitlement_id, **kwargs)

    @functools.wraps(entitlements.consume_entitlement)
    async def consume_entitlement(self, application_id, entitlement_id, **kwargs):
        return await entitlements.consume_entitlement(application_id, entitlement_id, **kwargs)

    @functools.wraps(entitlements.create_test_entitlement)
    async def create_test_entitlement(self, application_id, sku_id, owner_id, owner_type, **kwargs):
        return await entitlements.create_test_entitlement(application_id, sku_id, owner_id, owner_type, **kwargs)

    @functools.wraps(entitlements.delete_test_entitlement)
    async def delete_test_entitlement(self, application_id, entitlement_id, **kwargs):
        return await entitlements.delete_test_entitlement(application_id, entitlement_id, **kwargs)

    @functools.wraps(skus.fetch_skus)
    async def fetch_skus(self, application_id, **kwargs):
        return await skus.fetch_skus(application_id, **kwargs)

    @functools.wraps(subscriptions.fetch_sku_subscriptions)
    async def fetch_sku_subscriptions(self, sku_id, **kwargs):
        return await subscriptions.fetch_sku_subscriptions(sku_id, **kwargs)

    @functools.wraps(subscriptions.fetch_sku_subscription)
    async def fetch_sku_subscription(self, sku_id, subscription_id, **kwargs):
        return await subscriptions.fetch_sku_subscription(sku_id, subscription_id, **kwargs)

    # -- users --
    @functools.wraps(users.fetch_current_user)
    async def fetch_current_user(self, **kwargs):
        return await users.fetch_current_user(**kwargs)

    @functools.wraps(users.fetch_user)
    async def fetch_user(self, user_id, **kwargs):
        return await users.fetch_user(user_id, **kwargs)

    @functools.wraps(users.edit_current_user)
    async def edit_current_user(self, **kwargs):
        return await users.edit_current_user(**kwargs)

    @functools.wraps(users.fetch_current_user_guilds)
    async def fetch_current_user_guilds(self, **kwargs):
        return await users.fetch_current_user_guilds(**kwargs)

    @functools.wraps(users.leave_guild)
    async def leave_guild(self, guild_id, **kwargs):
        return await users.leave_guild(guild_id, **kwargs)

    @functools.wraps(users.create_dm)
    async def create_dm(self, recipient_id, **kwargs):
        return await users.create_dm(recipient_id, **kwargs)

    # -- audit log --
    @functools.wraps(audit_log.fetch_audit_log)
    async def fetch_audit_log(self, guild_id, **kwargs):
        return await audit_log.fetch_audit_log(guild_id, **kwargs)

    # -- guild templates --
    @functools.wraps(templates.fetch_template)
    async def fetch_template(self, code, **kwargs):
        return await templates.fetch_template(code, **kwargs)

    @functools.wraps(templates.fetch_guild_templates)
    async def fetch_guild_templates(self, guild_id, **kwargs):
        return await templates.fetch_guild_templates(guild_id, **kwargs)

    @functools.wraps(templates.create_guild_template)
    async def create_guild_template(self, guild_id, name, **kwargs):
        return await templates.create_guild_template(guild_id, name, **kwargs)

    @functools.wraps(templates.sync_guild_template)
    async def sync_guild_template(self, guild_id, code, **kwargs):
        return await templates.sync_guild_template(guild_id, code, **kwargs)

    @functools.wraps(templates.edit_guild_template)
    async def edit_guild_template(self, guild_id, code, **kwargs):
        return await templates.edit_guild_template(guild_id, code, **kwargs)

    @functools.wraps(templates.delete_guild_template)
    async def delete_guild_template(self, guild_id, code, **kwargs):
        return await templates.delete_guild_template(guild_id, code, **kwargs)

    # -- stage instances --
    @functools.wraps(stage_instances.create_stage_instance)
    async def create_stage_instance(self, channel_id, topic, **kwargs):
        return await stage_instances.create_stage_instance(channel_id, topic, **kwargs)

    @functools.wraps(stage_instances.fetch_stage_instance)
    async def fetch_stage_instance(self, channel_id, **kwargs):
        return await stage_instances.fetch_stage_instance(channel_id, **kwargs)

    @functools.wraps(stage_instances.edit_stage_instance)
    async def edit_stage_instance(self, channel_id, **kwargs):
        return await stage_instances.edit_stage_instance(channel_id, **kwargs)

    @functools.wraps(stage_instances.delete_stage_instance)
    async def delete_stage_instance(self, channel_id, **kwargs):
        return await stage_instances.delete_stage_instance(channel_id, **kwargs)

    # -- auto moderation --
    @functools.wraps(auto_moderation.fetch_auto_moderation_rules)
    async def fetch_auto_moderation_rules(self, guild_id, **kwargs):
        return await auto_moderation.fetch_auto_moderation_rules(guild_id, **kwargs)

    @functools.wraps(auto_moderation.fetch_auto_moderation_rule)
    async def fetch_auto_moderation_rule(self, guild_id, rule_id, **kwargs):
        return await auto_moderation.fetch_auto_moderation_rule(guild_id, rule_id, **kwargs)

    @functools.wraps(auto_moderation.create_auto_moderation_rule)
    async def create_auto_moderation_rule(self, guild_id, name, event_type, trigger_type, actions, **kwargs):
        return await auto_moderation.create_auto_moderation_rule(
            guild_id, name, event_type, trigger_type, actions, **kwargs
        )

    @functools.wraps(auto_moderation.edit_auto_moderation_rule)
    async def edit_auto_moderation_rule(self, guild_id, rule_id, **kwargs):
        return await auto_moderation.edit_auto_moderation_rule(guild_id, rule_id, **kwargs)

    @functools.wraps(auto_moderation.delete_auto_moderation_rule)
    async def delete_auto_moderation_rule(self, guild_id, rule_id, **kwargs):
        return await auto_moderation.delete_auto_moderation_rule(guild_id, rule_id, **kwargs)

    # -- guild scheduled events --
    @functools.wraps(scheduled_events.fetch_guild_scheduled_events)
    async def fetch_guild_scheduled_events(self, guild_id, **kwargs):
        return await scheduled_events.fetch_guild_scheduled_events(guild_id, **kwargs)

    @functools.wraps(scheduled_events.create_guild_scheduled_event)
    async def create_guild_scheduled_event(
        self, guild_id, name, privacy_level, scheduled_start_time, entity_type, **kwargs
    ):
        return await scheduled_events.create_guild_scheduled_event(
            guild_id, name, privacy_level, scheduled_start_time, entity_type, **kwargs
        )

    @functools.wraps(scheduled_events.fetch_guild_scheduled_event)
    async def fetch_guild_scheduled_event(self, guild_id, event_id, **kwargs):
        return await scheduled_events.fetch_guild_scheduled_event(guild_id, event_id, **kwargs)

    @functools.wraps(scheduled_events.edit_guild_scheduled_event)
    async def edit_guild_scheduled_event(self, guild_id, event_id, **kwargs):
        return await scheduled_events.edit_guild_scheduled_event(guild_id, event_id, **kwargs)

    @functools.wraps(scheduled_events.delete_guild_scheduled_event)
    async def delete_guild_scheduled_event(self, guild_id, event_id, **kwargs):
        return await scheduled_events.delete_guild_scheduled_event(guild_id, event_id, **kwargs)

    @functools.wraps(scheduled_events.fetch_guild_scheduled_event_users)
    async def fetch_guild_scheduled_event_users(self, guild_id, event_id, **kwargs):
        return await scheduled_events.fetch_guild_scheduled_event_users(guild_id, event_id, **kwargs)

    @functools.wraps(scheduled_events.fetch_guild_scheduled_event_user_counts)
    async def fetch_guild_scheduled_event_user_counts(self, guild_id, event_id, **kwargs):
        return await scheduled_events.fetch_guild_scheduled_event_user_counts(guild_id, event_id, **kwargs)

    @functools.wraps(scheduled_events.create_guild_scheduled_event_exception)
    async def create_guild_scheduled_event_exception(self, guild_id, event_id, original_scheduled_start_time, **kwargs):
        return await scheduled_events.create_guild_scheduled_event_exception(
            guild_id, event_id, original_scheduled_start_time, **kwargs
        )

    @functools.wraps(scheduled_events.edit_guild_scheduled_event_exception)
    async def edit_guild_scheduled_event_exception(self, guild_id, event_id, exception_id, **kwargs):
        return await scheduled_events.edit_guild_scheduled_event_exception(guild_id, event_id, exception_id, **kwargs)

    @functools.wraps(scheduled_events.delete_guild_scheduled_event_exception)
    async def delete_guild_scheduled_event_exception(self, guild_id, event_id, exception_id, **kwargs):
        return await scheduled_events.delete_guild_scheduled_event_exception(guild_id, event_id, exception_id, **kwargs)

    @functools.wraps(scheduled_events.fetch_guild_scheduled_event_exception_users)
    async def fetch_guild_scheduled_event_exception_users(self, guild_id, event_id, exception_id, **kwargs):
        return await scheduled_events.fetch_guild_scheduled_event_exception_users(
            guild_id, event_id, exception_id, **kwargs
        )

    # -- emojis --
    @functools.wraps(emojis.fetch_guild_emojis)
    async def fetch_guild_emojis(self, guild_id, **kwargs):
        return await emojis.fetch_guild_emojis(guild_id, **kwargs)

    @functools.wraps(emojis.fetch_guild_emoji)
    async def fetch_guild_emoji(self, guild_id, emoji_id, **kwargs):
        return await emojis.fetch_guild_emoji(guild_id, emoji_id, **kwargs)

    @functools.wraps(emojis.create_guild_emoji)
    async def create_guild_emoji(self, guild_id, name, image, **kwargs):
        return await emojis.create_guild_emoji(guild_id, name, image, **kwargs)

    @functools.wraps(emojis.edit_guild_emoji)
    async def edit_guild_emoji(self, guild_id, emoji_id, **kwargs):
        return await emojis.edit_guild_emoji(guild_id, emoji_id, **kwargs)

    @functools.wraps(emojis.delete_guild_emoji)
    async def delete_guild_emoji(self, guild_id, emoji_id, **kwargs):
        return await emojis.delete_guild_emoji(guild_id, emoji_id, **kwargs)

    @functools.wraps(emojis.fetch_application_emojis)
    async def fetch_application_emojis(self, application_id, **kwargs):
        return await emojis.fetch_application_emojis(application_id, **kwargs)

    @functools.wraps(emojis.fetch_application_emoji)
    async def fetch_application_emoji(self, application_id, emoji_id, **kwargs):
        return await emojis.fetch_application_emoji(application_id, emoji_id, **kwargs)

    @functools.wraps(emojis.create_application_emoji)
    async def create_application_emoji(self, application_id, name, image, **kwargs):
        return await emojis.create_application_emoji(application_id, name, image, **kwargs)

    @functools.wraps(emojis.edit_application_emoji)
    async def edit_application_emoji(self, application_id, emoji_id, **kwargs):
        return await emojis.edit_application_emoji(application_id, emoji_id, **kwargs)

    @functools.wraps(emojis.delete_application_emoji)
    async def delete_application_emoji(self, application_id, emoji_id, **kwargs):
        return await emojis.delete_application_emoji(application_id, emoji_id, **kwargs)

    # -- soundboard --
    @functools.wraps(soundboard.send_soundboard_sound)
    async def send_soundboard_sound(self, channel_id, sound_id, **kwargs):
        await soundboard.send_soundboard_sound(channel_id, sound_id, **kwargs)

    @functools.wraps(soundboard.fetch_default_soundboard_sounds)
    async def fetch_default_soundboard_sounds(self, **kwargs):
        return await soundboard.fetch_default_soundboard_sounds(**kwargs)

    @functools.wraps(soundboard.fetch_guild_soundboard_sounds)
    async def fetch_guild_soundboard_sounds(self, guild_id, **kwargs):
        return await soundboard.fetch_guild_soundboard_sounds(guild_id, **kwargs)

    @functools.wraps(soundboard.fetch_guild_soundboard_sound)
    async def fetch_guild_soundboard_sound(self, guild_id, sound_id, **kwargs):
        return await soundboard.fetch_guild_soundboard_sound(guild_id, sound_id, **kwargs)

    @functools.wraps(soundboard.create_guild_soundboard_sound)
    async def create_guild_soundboard_sound(self, guild_id, name, sound, **kwargs):
        return await soundboard.create_guild_soundboard_sound(guild_id, name, sound, **kwargs)

    @functools.wraps(soundboard.edit_guild_soundboard_sound)
    async def edit_guild_soundboard_sound(self, guild_id, sound_id, **kwargs):
        return await soundboard.edit_guild_soundboard_sound(guild_id, sound_id, **kwargs)

    @functools.wraps(soundboard.delete_guild_soundboard_sound)
    async def delete_guild_soundboard_sound(self, guild_id, sound_id, **kwargs):
        await soundboard.delete_guild_soundboard_sound(guild_id, sound_id, **kwargs)

    # -- stickers --
    @functools.wraps(stickers.fetch_sticker)
    async def fetch_sticker(self, sticker_id, **kwargs):
        return await stickers.fetch_sticker(sticker_id, **kwargs)

    @functools.wraps(stickers.fetch_sticker_packs)
    async def fetch_sticker_packs(self, **kwargs):
        return await stickers.fetch_sticker_packs(**kwargs)

    @functools.wraps(stickers.fetch_sticker_pack)
    async def fetch_sticker_pack(self, pack_id, **kwargs):
        return await stickers.fetch_sticker_pack(pack_id, **kwargs)

    @functools.wraps(stickers.fetch_guild_stickers)
    async def fetch_guild_stickers(self, guild_id, **kwargs):
        return await stickers.fetch_guild_stickers(guild_id, **kwargs)

    @functools.wraps(stickers.fetch_guild_sticker)
    async def fetch_guild_sticker(self, guild_id, sticker_id, **kwargs):
        return await stickers.fetch_guild_sticker(guild_id, sticker_id, **kwargs)

    @functools.wraps(stickers.create_guild_sticker)
    async def create_guild_sticker(self, guild_id, name, description, tags, filename, file_bytes, **kwargs):
        return await stickers.create_guild_sticker(guild_id, name, description, tags, filename, file_bytes, **kwargs)

    @functools.wraps(stickers.edit_guild_sticker)
    async def edit_guild_sticker(self, guild_id, sticker_id, **kwargs):
        return await stickers.edit_guild_sticker(guild_id, sticker_id, **kwargs)

    @functools.wraps(stickers.delete_guild_sticker)
    async def delete_guild_sticker(self, guild_id, sticker_id, **kwargs):
        return await stickers.delete_guild_sticker(guild_id, sticker_id, **kwargs)

    # -- invites --
    @functools.wraps(invites.fetch_invite)
    async def fetch_invite(self, code, **kwargs):
        return await invites.fetch_invite(code, **kwargs)

    @functools.wraps(invites.delete_invite)
    async def delete_invite(self, code, **kwargs):
        return await invites.delete_invite(code, **kwargs)

    @functools.wraps(invites.fetch_invite_target_users)
    async def fetch_invite_target_users(self, code, **kwargs):
        return await invites.fetch_invite_target_users(code, **kwargs)

    @functools.wraps(invites.edit_invite_target_users)
    async def edit_invite_target_users(self, code, filename, file_bytes, **kwargs):
        await invites.edit_invite_target_users(code, filename, file_bytes, **kwargs)

    @functools.wraps(invites.fetch_invite_target_users_job_status)
    async def fetch_invite_target_users_job_status(self, code, **kwargs):
        return await invites.fetch_invite_target_users_job_status(code, **kwargs)

    # -- webhooks (bot token) --
    # create_webhook()/get_channel_webhooks()/delete_webhook() already live
    # directly on Cordless (see app.py) and delegate to webhooks.py
    # themselves, same reason messages.py has no bot.create_message().
    @functools.wraps(webhooks.fetch_channel_webhooks)
    async def fetch_channel_webhooks(self, channel_id, **kwargs):
        return await webhooks.fetch_channel_webhooks(channel_id, **kwargs)

    @functools.wraps(webhooks.fetch_guild_webhooks)
    async def fetch_guild_webhooks(self, guild_id, **kwargs):
        return await webhooks.fetch_guild_webhooks(guild_id, **kwargs)

    @functools.wraps(webhooks.fetch_webhook)
    async def fetch_webhook(self, webhook_id, **kwargs):
        return await webhooks.fetch_webhook(webhook_id, **kwargs)

    @functools.wraps(webhooks.edit_webhook)
    async def edit_webhook(self, webhook_id, **kwargs):
        return await webhooks.edit_webhook(webhook_id, **kwargs)

    # -- messages and reactions --
    # no bot.create_message()/edit_message() here on purpose - send_message()
    # and edit_message() already own those verbs directly on Cordless (see
    # app.py) and delegate to messages.py themselves; a second, similarly
    # named flat method would just be confusing. Use channel.send() or
    # message.edit() for the fuller field set.
    @functools.wraps(messages.fetch_channel_messages)
    async def fetch_channel_messages(self, channel_id, **kwargs):
        return await messages.fetch_channel_messages(channel_id, **kwargs)

    @functools.wraps(messages.fetch_message)
    async def fetch_message(self, channel_id, message_id, **kwargs):
        return await messages.fetch_message(channel_id, message_id, **kwargs)

    @functools.wraps(messages.crosspost_message)
    async def crosspost_message(self, channel_id, message_id, **kwargs):
        return await messages.crosspost_message(channel_id, message_id, **kwargs)

    @functools.wraps(messages.bulk_delete_messages)
    async def bulk_delete_messages(self, channel_id, message_ids, **kwargs):
        return await messages.bulk_delete_messages(channel_id, message_ids, **kwargs)

    @functools.wraps(messages.create_reaction)
    async def create_reaction(self, channel_id, message_id, emoji, **kwargs):
        return await messages.create_reaction(channel_id, message_id, emoji, **kwargs)

    @functools.wraps(messages.delete_own_reaction)
    async def delete_own_reaction(self, channel_id, message_id, emoji, **kwargs):
        return await messages.delete_own_reaction(channel_id, message_id, emoji, **kwargs)

    @functools.wraps(messages.delete_user_reaction)
    async def delete_user_reaction(self, channel_id, message_id, emoji, user_id, **kwargs):
        return await messages.delete_user_reaction(channel_id, message_id, emoji, user_id, **kwargs)

    @functools.wraps(messages.fetch_reactions)
    async def fetch_reactions(self, channel_id, message_id, emoji, **kwargs):
        return await messages.fetch_reactions(channel_id, message_id, emoji, **kwargs)

    @functools.wraps(messages.delete_all_reactions)
    async def delete_all_reactions(self, channel_id, message_id, **kwargs):
        return await messages.delete_all_reactions(channel_id, message_id, **kwargs)

    @functools.wraps(messages.delete_all_reactions_for_emoji)
    async def delete_all_reactions_for_emoji(self, channel_id, message_id, emoji, **kwargs):
        return await messages.delete_all_reactions_for_emoji(channel_id, message_id, emoji, **kwargs)

    @functools.wraps(messages.search_guild_messages)
    async def search_guild_messages(self, guild_id, **kwargs):
        return await messages.search_guild_messages(guild_id, **kwargs)

    @functools.wraps(messages.fetch_poll_answer_voters)
    async def fetch_poll_answer_voters(self, channel_id, message_id, answer_id, **kwargs):
        return await messages.fetch_poll_answer_voters(channel_id, message_id, answer_id, **kwargs)

    @functools.wraps(messages.expire_poll)
    async def expire_poll(self, channel_id, message_id, **kwargs):
        return await messages.expire_poll(channel_id, message_id, **kwargs)

    # -- members and roles --
    @functools.wraps(members.fetch_guild_member)
    async def fetch_guild_member(self, guild_id, user_id, **kwargs):
        return await members.fetch_guild_member(guild_id, user_id, **kwargs)

    @functools.wraps(members.fetch_guild_members)
    async def fetch_guild_members(self, guild_id, **kwargs):
        return await members.fetch_guild_members(guild_id, **kwargs)

    @functools.wraps(members.search_guild_members)
    async def search_guild_members(self, guild_id, query, **kwargs):
        return await members.search_guild_members(guild_id, query, **kwargs)

    @functools.wraps(members.add_guild_member)
    async def add_guild_member(self, guild_id, user_id, access_token, **kwargs):
        return await members.add_guild_member(guild_id, user_id, access_token, **kwargs)

    @functools.wraps(members.edit_guild_member)
    async def edit_guild_member(self, guild_id, user_id, **kwargs):
        return await members.edit_guild_member(guild_id, user_id, **kwargs)

    @functools.wraps(members.edit_current_member)
    async def edit_current_member(self, guild_id, **kwargs):
        return await members.edit_current_member(guild_id, **kwargs)

    @functools.wraps(members.add_guild_member_role)
    async def add_guild_member_role(self, guild_id, user_id, role_id, **kwargs):
        return await members.add_guild_member_role(guild_id, user_id, role_id, **kwargs)

    @functools.wraps(members.remove_guild_member_role)
    async def remove_guild_member_role(self, guild_id, user_id, role_id, **kwargs):
        return await members.remove_guild_member_role(guild_id, user_id, role_id, **kwargs)

    @functools.wraps(members.remove_guild_member)
    async def remove_guild_member(self, guild_id, user_id, **kwargs):
        return await members.remove_guild_member(guild_id, user_id, **kwargs)

    @functools.wraps(members.fetch_guild_roles)
    async def fetch_guild_roles(self, guild_id, **kwargs):
        return await members.fetch_guild_roles(guild_id, **kwargs)

    @functools.wraps(members.fetch_guild_role)
    async def fetch_guild_role(self, guild_id, role_id, **kwargs):
        return await members.fetch_guild_role(guild_id, role_id, **kwargs)

    @functools.wraps(members.fetch_guild_role_member_counts)
    async def fetch_guild_role_member_counts(self, guild_id, **kwargs):
        return await members.fetch_guild_role_member_counts(guild_id, **kwargs)

    @functools.wraps(members.create_guild_role)
    async def create_guild_role(self, guild_id, **kwargs):
        return await members.create_guild_role(guild_id, **kwargs)

    @functools.wraps(members.edit_guild_role_positions)
    async def edit_guild_role_positions(self, guild_id, positions, **kwargs):
        return await members.edit_guild_role_positions(guild_id, positions, **kwargs)

    @functools.wraps(members.edit_guild_role)
    async def edit_guild_role(self, guild_id, role_id, **kwargs):
        return await members.edit_guild_role(guild_id, role_id, **kwargs)

    @functools.wraps(members.delete_guild_role)
    async def delete_guild_role(self, guild_id, role_id, **kwargs):
        return await members.delete_guild_role(guild_id, role_id, **kwargs)

    # -- guilds --
    @functools.wraps(guilds.fetch_guild)
    async def fetch_guild(self, guild_id, **kwargs):
        return await guilds.fetch_guild(guild_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_preview)
    async def fetch_guild_preview(self, guild_id, **kwargs):
        return await guilds.fetch_guild_preview(guild_id, **kwargs)

    @functools.wraps(guilds.edit_guild)
    async def edit_guild(self, guild_id, **kwargs):
        return await guilds.edit_guild(guild_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_bans)
    async def fetch_guild_bans(self, guild_id, **kwargs):
        return await guilds.fetch_guild_bans(guild_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_ban)
    async def fetch_guild_ban(self, guild_id, user_id, **kwargs):
        return await guilds.fetch_guild_ban(guild_id, user_id, **kwargs)

    @functools.wraps(guilds.create_guild_ban)
    async def create_guild_ban(self, guild_id, user_id, **kwargs):
        return await guilds.create_guild_ban(guild_id, user_id, **kwargs)

    @functools.wraps(guilds.remove_guild_ban)
    async def remove_guild_ban(self, guild_id, user_id, **kwargs):
        return await guilds.remove_guild_ban(guild_id, user_id, **kwargs)

    @functools.wraps(guilds.bulk_guild_ban)
    async def bulk_guild_ban(self, guild_id, user_ids, **kwargs):
        return await guilds.bulk_guild_ban(guild_id, user_ids, **kwargs)

    @functools.wraps(guilds.fetch_guild_prune_count)
    async def fetch_guild_prune_count(self, guild_id, **kwargs):
        return await guilds.fetch_guild_prune_count(guild_id, **kwargs)

    @functools.wraps(guilds.begin_guild_prune)
    async def begin_guild_prune(self, guild_id, **kwargs):
        return await guilds.begin_guild_prune(guild_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_voice_regions)
    async def fetch_guild_voice_regions(self, guild_id, **kwargs):
        return await guilds.fetch_guild_voice_regions(guild_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_invites)
    async def fetch_guild_invites(self, guild_id, **kwargs):
        return await guilds.fetch_guild_invites(guild_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_integrations)
    async def fetch_guild_integrations(self, guild_id, **kwargs):
        return await guilds.fetch_guild_integrations(guild_id, **kwargs)

    @functools.wraps(guilds.delete_guild_integration)
    async def delete_guild_integration(self, guild_id, integration_id, **kwargs):
        return await guilds.delete_guild_integration(guild_id, integration_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_widget_settings)
    async def fetch_guild_widget_settings(self, guild_id, **kwargs):
        return await guilds.fetch_guild_widget_settings(guild_id, **kwargs)

    @functools.wraps(guilds.edit_guild_widget)
    async def edit_guild_widget(self, guild_id, **kwargs):
        return await guilds.edit_guild_widget(guild_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_widget)
    async def fetch_guild_widget(self, guild_id, **kwargs):
        return await guilds.fetch_guild_widget(guild_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_vanity_url)
    async def fetch_guild_vanity_url(self, guild_id, **kwargs):
        return await guilds.fetch_guild_vanity_url(guild_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_welcome_screen)
    async def fetch_guild_welcome_screen(self, guild_id, **kwargs):
        return await guilds.fetch_guild_welcome_screen(guild_id, **kwargs)

    @functools.wraps(guilds.edit_guild_welcome_screen)
    async def edit_guild_welcome_screen(self, guild_id, **kwargs):
        return await guilds.edit_guild_welcome_screen(guild_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_onboarding)
    async def fetch_guild_onboarding(self, guild_id, **kwargs):
        return await guilds.fetch_guild_onboarding(guild_id, **kwargs)

    @functools.wraps(guilds.edit_guild_onboarding)
    async def edit_guild_onboarding(self, guild_id, **kwargs):
        return await guilds.edit_guild_onboarding(guild_id, **kwargs)

    @functools.wraps(guilds.edit_guild_incident_actions)
    async def edit_guild_incident_actions(self, guild_id, **kwargs):
        return await guilds.edit_guild_incident_actions(guild_id, **kwargs)

    @functools.wraps(guilds.fetch_guild_new_member_welcome)
    async def fetch_guild_new_member_welcome(self, guild_id, **kwargs):
        return await guilds.fetch_guild_new_member_welcome(guild_id, **kwargs)

    # -- guild join requests --
    @functools.wraps(guild_requests.fetch_guild_join_requests)
    async def fetch_guild_join_requests(self, guild_id, **kwargs):
        return await guild_requests.fetch_guild_join_requests(guild_id, **kwargs)

    @functools.wraps(guild_requests.edit_guild_join_request)
    async def edit_guild_join_request(self, guild_id, request_id, action, **kwargs):
        return await guild_requests.edit_guild_join_request(guild_id, request_id, action, **kwargs)

    # -- channels --
    @functools.wraps(channels.fetch_channel)
    async def fetch_channel(self, channel_id, **kwargs):
        return await channels.fetch_channel(channel_id, **kwargs)

    @functools.wraps(channels.edit_channel)
    async def edit_channel(self, channel_id, **kwargs):
        return await channels.edit_channel(channel_id, **kwargs)

    @functools.wraps(channels.delete_channel)
    async def delete_channel(self, channel_id, **kwargs):
        return await channels.delete_channel(channel_id, **kwargs)

    @functools.wraps(channels.edit_channel_permissions)
    async def edit_channel_permissions(self, channel_id, overwrite_id, **kwargs):
        return await channels.edit_channel_permissions(channel_id, overwrite_id, **kwargs)

    @functools.wraps(channels.delete_channel_permission)
    async def delete_channel_permission(self, channel_id, overwrite_id, **kwargs):
        return await channels.delete_channel_permission(channel_id, overwrite_id, **kwargs)

    @functools.wraps(channels.fetch_channel_invites)
    async def fetch_channel_invites(self, channel_id, **kwargs):
        return await channels.fetch_channel_invites(channel_id, **kwargs)

    @functools.wraps(channels.create_channel_invite)
    async def create_channel_invite(self, channel_id, **kwargs):
        return await channels.create_channel_invite(channel_id, **kwargs)

    @functools.wraps(channels.follow_announcement_channel)
    async def follow_announcement_channel(self, channel_id, webhook_channel_id, **kwargs):
        return await channels.follow_announcement_channel(channel_id, webhook_channel_id, **kwargs)

    @functools.wraps(channels.trigger_typing)
    async def trigger_typing(self, channel_id, **kwargs):
        return await channels.trigger_typing(channel_id, **kwargs)

    @functools.wraps(channels.set_voice_channel_status)
    async def set_voice_channel_status(self, channel_id, status=None, **kwargs):
        return await channels.set_voice_channel_status(channel_id, status, **kwargs)

    @functools.wraps(channels.add_group_dm_recipient)
    async def add_group_dm_recipient(self, channel_id, user_id, access_token, **kwargs):
        return await channels.add_group_dm_recipient(channel_id, user_id, access_token, **kwargs)

    @functools.wraps(channels.remove_group_dm_recipient)
    async def remove_group_dm_recipient(self, channel_id, user_id, **kwargs):
        return await channels.remove_group_dm_recipient(channel_id, user_id, **kwargs)

    @functools.wraps(channels.fetch_channel_pins)
    async def fetch_channel_pins(self, channel_id, **kwargs):
        return await channels.fetch_channel_pins(channel_id, **kwargs)

    @functools.wraps(channels.pin_message)
    async def pin_message(self, channel_id, message_id, **kwargs):
        return await channels.pin_message(channel_id, message_id, **kwargs)

    @functools.wraps(channels.unpin_message)
    async def unpin_message(self, channel_id, message_id, **kwargs):
        return await channels.unpin_message(channel_id, message_id, **kwargs)

    @functools.wraps(channels.fetch_guild_channels)
    async def fetch_guild_channels(self, guild_id, **kwargs):
        return await channels.fetch_guild_channels(guild_id, **kwargs)

    @functools.wraps(channels.create_guild_channel)
    async def create_guild_channel(self, guild_id, name, **kwargs):
        return await channels.create_guild_channel(guild_id, name, **kwargs)

    @functools.wraps(channels.edit_guild_channel_positions)
    async def edit_guild_channel_positions(self, guild_id, positions, **kwargs):
        return await channels.edit_guild_channel_positions(guild_id, positions, **kwargs)

    # -- threads --
    @functools.wraps(threads.start_thread_from_message)
    async def start_thread_from_message(self, channel_id, message_id, name, **kwargs):
        return await threads.start_thread_from_message(channel_id, message_id, name, **kwargs)

    @functools.wraps(threads.start_thread_without_message)
    async def start_thread_without_message(self, channel_id, name, **kwargs):
        return await threads.start_thread_without_message(channel_id, name, **kwargs)

    @functools.wraps(threads.start_thread_from_forum)
    async def start_thread_from_forum(self, channel_id, name, **kwargs):
        return await threads.start_thread_from_forum(channel_id, name, **kwargs)

    @functools.wraps(threads.join_thread)
    async def join_thread(self, channel_id, **kwargs):
        return await threads.join_thread(channel_id, **kwargs)

    @functools.wraps(threads.leave_thread)
    async def leave_thread(self, channel_id, **kwargs):
        return await threads.leave_thread(channel_id, **kwargs)

    @functools.wraps(threads.add_thread_member)
    async def add_thread_member(self, channel_id, user_id, **kwargs):
        return await threads.add_thread_member(channel_id, user_id, **kwargs)

    @functools.wraps(threads.remove_thread_member)
    async def remove_thread_member(self, channel_id, user_id, **kwargs):
        return await threads.remove_thread_member(channel_id, user_id, **kwargs)

    @functools.wraps(threads.fetch_thread_member)
    async def fetch_thread_member(self, channel_id, user_id, **kwargs):
        return await threads.fetch_thread_member(channel_id, user_id, **kwargs)

    @functools.wraps(threads.fetch_thread_members)
    async def fetch_thread_members(self, channel_id, **kwargs):
        return await threads.fetch_thread_members(channel_id, **kwargs)

    @functools.wraps(threads.fetch_public_archived_threads)
    async def fetch_public_archived_threads(self, channel_id, **kwargs):
        return await threads.fetch_public_archived_threads(channel_id, **kwargs)

    @functools.wraps(threads.fetch_private_archived_threads)
    async def fetch_private_archived_threads(self, channel_id, **kwargs):
        return await threads.fetch_private_archived_threads(channel_id, **kwargs)

    @functools.wraps(threads.fetch_joined_private_archived_threads)
    async def fetch_joined_private_archived_threads(self, channel_id, **kwargs):
        return await threads.fetch_joined_private_archived_threads(channel_id, **kwargs)

    @functools.wraps(threads.fetch_active_guild_threads)
    async def fetch_active_guild_threads(self, guild_id, **kwargs):
        return await threads.fetch_active_guild_threads(guild_id, **kwargs)

    @functools.wraps(threads.search_channel_threads)
    async def search_channel_threads(self, channel_id, **kwargs):
        return await threads.search_channel_threads(channel_id, **kwargs)

    # -- voice --
    @functools.wraps(voice.fetch_voice_regions)
    async def fetch_voice_regions(self, **kwargs):
        return await voice.fetch_voice_regions(**kwargs)

    @functools.wraps(voice.fetch_current_user_voice_state)
    async def fetch_guild_current_voice_state(self, guild_id, **kwargs):
        return await voice.fetch_current_user_voice_state(guild_id, **kwargs)

    @functools.wraps(voice.fetch_user_voice_state)
    async def fetch_guild_member_voice_state(self, guild_id, user_id, **kwargs):
        return await voice.fetch_user_voice_state(guild_id, user_id, **kwargs)

    @functools.wraps(voice.edit_current_user_voice_state)
    async def edit_guild_current_voice_state(self, guild_id, **kwargs):
        await voice.edit_current_user_voice_state(guild_id, **kwargs)

    @functools.wraps(voice.edit_user_voice_state)
    async def edit_guild_member_voice_state(self, guild_id, user_id, **kwargs):
        await voice.edit_user_voice_state(guild_id, user_id, **kwargs)
