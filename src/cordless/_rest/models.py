"""Shared dataclasses for REST responses.

Passive data containers only - named attributes plus read-only convenience
properties computed from that object's own payload. No back-reference to a
Cordless instance and no action methods: every action already exists as a
flat method on bot itself (bot.send_message(channel.id, ...) etc.), so a
returned object never needs its own .send()/.edit()/.delete().
"""

from dataclasses import dataclass, field


class _FromDict:
    """Parses only known fields; ignores whatever new keys Discord adds later
    instead of raising, so a schema addition doesn't break existing bots."""

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
