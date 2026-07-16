"""RESTMixin: the flat bot.<verb>_<resource>() surface.

One mixin, not one per resource - Cordless(RESTMixin) is ordinary single
inheritance. Every method here is a thin delegation to a resource module's
free function; the actual request-building/response-parsing logic lives in
those modules (threads.py, channels.py, ...), grouped by resource, so this
file stays pure boilerplate no matter how many resources it grows to cover.
"""

from . import threads


class RESTMixin:
    # -- threads --
    def start_thread_from_message(self, channel_id, message_id, name, **kwargs):
        return threads.start_thread_from_message(channel_id, message_id, name, **kwargs)

    def start_thread_without_message(self, channel_id, name, **kwargs):
        return threads.start_thread_without_message(channel_id, name, **kwargs)

    def join_thread(self, channel_id):
        return threads.join_thread(channel_id)

    def leave_thread(self, channel_id):
        return threads.leave_thread(channel_id)

    def add_thread_member(self, channel_id, user_id):
        return threads.add_thread_member(channel_id, user_id)

    def remove_thread_member(self, channel_id, user_id):
        return threads.remove_thread_member(channel_id, user_id)

    def fetch_thread_members(self, channel_id, **kwargs):
        return threads.fetch_thread_members(channel_id, **kwargs)

    def fetch_public_archived_threads(self, channel_id, **kwargs):
        return threads.fetch_public_archived_threads(channel_id, **kwargs)
