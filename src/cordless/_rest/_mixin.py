"""RESTMixin: the flat bot.<verb>_<resource>() surface.

One mixin, not one per resource - Cordless(RESTMixin) is ordinary single
inheritance. Every method here is a thin delegation to a resource module's
free function; the actual request-building/response-parsing logic lives in
those modules (threads.py, channels.py, ...), grouped by resource, so this
file stays pure boilerplate no matter how many resources it grows to cover.

Every method is async, matching the rest of Cordless's public REST surface
(send_message, execute_webhook, ...): await bot.start_thread_from_message(...).
"""

from . import threads


class RESTMixin:
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
