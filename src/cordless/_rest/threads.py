"""Thread REST endpoints (Discord API v10)."""

from . import _client
from .models import Thread, ThreadMember


def start_thread_from_message(channel_id, message_id, name, *, auto_archive_duration=None, token=None):
    payload = {"name": name}
    if auto_archive_duration is not None:
        payload["auto_archive_duration"] = auto_archive_duration
    data = _client.request("POST", f"/channels/{channel_id}/messages/{message_id}/threads", payload, token=token)
    return Thread.from_dict(data)


def start_thread_without_message(channel_id, name, *, thread_type=11, invitable=None, token=None):
    payload = {"name": name, "type": thread_type}
    if invitable is not None:
        payload["invitable"] = invitable
    data = _client.request("POST", f"/channels/{channel_id}/threads", payload, token=token)
    return Thread.from_dict(data)


def join_thread(channel_id, token=None):
    _client.request("PUT", f"/channels/{channel_id}/thread-members/@me", token=token)


def leave_thread(channel_id, token=None):
    _client.request("DELETE", f"/channels/{channel_id}/thread-members/@me", token=token)


def add_thread_member(channel_id, user_id, token=None):
    _client.request("PUT", f"/channels/{channel_id}/thread-members/{user_id}", token=token)


def remove_thread_member(channel_id, user_id, token=None):
    _client.request("DELETE", f"/channels/{channel_id}/thread-members/{user_id}", token=token)


def fetch_thread_members(channel_id, *, with_member=False, token=None):
    qs = "?with_member=true" if with_member else ""
    data = _client.request("GET", f"/channels/{channel_id}/thread-members{qs}", token=token)
    return [ThreadMember.from_dict(m) for m in data]


def fetch_public_archived_threads(channel_id, *, before=None, limit=None, token=None):
    params = [p for p in (f"before={before}" if before else None, f"limit={limit}" if limit else None) if p]
    qs = ("?" + "&".join(params)) if params else ""
    data = _client.request("GET", f"/channels/{channel_id}/threads/archived/public{qs}", token=token)
    return [Thread.from_dict(t) for t in data["threads"]]
