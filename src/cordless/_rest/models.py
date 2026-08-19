"""Shared dataclasses for REST responses.

Carry read-only convenience properties plus thin action methods (e.g.
thread.join()), but never a back-reference to a Cordless instance. Each
action method is a straight delegation to the same _rest/<resource>.py
function bot.<verb>_<resource>() already calls, using only this object's own
id and, optionally, an explicit token kwarg - both call shapes hit the exact
same code path, so there is no request logic duplicated between them.
"""

from dataclasses import Field, dataclass, field
from typing import ClassVar


class _FromDict:
    """Parses only known fields; ignores whatever new keys Discord adds later
    instead of raising, so a schema addition doesn't break existing bots."""

    # Declares the contract every subclass must satisfy (being an actual
    # @dataclass) so pyright can see __dataclass_fields__ below, since
    # _FromDict itself isn't decorated with @dataclass.
    __dataclass_fields__: ClassVar[dict[str, Field]]

    @classmethod
    def from_dict(cls, data):
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class ThreadMember(_FromDict):
    id: str | None = None
    user_id: str | None = None
    join_timestamp: str | None = None
    flags: int = 0


@dataclass
class Thread(_FromDict):
    id: str
    guild_id: str | None
    parent_id: str | None
    owner_id: str | None
    name: str
    type: int
    message_count: int = 0
    member_count: int = 0
    thread_metadata: dict = field(default_factory=dict)
    rate_limit_per_user: int = 0

    @property
    def archived(self):
        return self.thread_metadata.get("archived", False)

    @property
    def locked(self):
        return self.thread_metadata.get("locked", False)

    @property
    def mention(self):
        return f"<#{self.id}>"

    async def join(self, *, token=None):
        """Join this thread as the bot. Requires `DISCORD_BOT_TOKEN`."""
        from . import threads

        await threads.join_thread(self.id, token=token)

    async def leave(self, *, token=None):
        """Leave this thread. Requires `DISCORD_BOT_TOKEN`."""
        from . import threads

        await threads.leave_thread(self.id, token=token)

    async def add_member(self, user_id, *, token=None):
        """Add a member to this thread. Requires `DISCORD_BOT_TOKEN`."""
        from . import threads

        await threads.add_thread_member(self.id, user_id, token=token)

    async def remove_member(self, user_id, *, token=None):
        """Remove a member from this thread. Requires `DISCORD_BOT_TOKEN`."""
        from . import threads

        await threads.remove_thread_member(self.id, user_id, token=token)

    async def fetch_member(self, user_id, *, with_member=False, token=None):
        """Fetch a single member of this thread, as a `ThreadMember`.
        Requires `DISCORD_BOT_TOKEN`."""
        from . import threads

        return await threads.fetch_thread_member(self.id, user_id, with_member=with_member, token=token)

    async def fetch_members(self, *, with_member=False, token=None):
        """List this thread's members, as a list of `ThreadMember`. Requires
        `DISCORD_BOT_TOKEN`."""
        from . import threads

        return await threads.fetch_thread_members(self.id, with_member=with_member, token=token)
