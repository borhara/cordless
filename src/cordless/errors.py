import email.message
from collections.abc import Mapping


class CordlessError(Exception):
    """Base exception for all cordless errors."""


class UnknownCommandError(CordlessError):
    """Raised when an interaction references a command with no registered handler."""


class UnknownButtonError(CordlessError):
    """Raised when an interaction references a custom_id with no registered handler."""


class UnsupportedInteractionError(CordlessError):
    """Raised when an interaction type is not handled by the router."""


class InvalidSignatureError(CordlessError):
    """Raised when a request fails Discord's Ed25519 signature verification."""


class NoResponseError(CordlessError):
    """Raised when a handler never calls ctx.send/edit/defer nor returns a response."""


class UnknownComponentError(CordlessError):
    """Raised when a select menu interaction has no registered handler."""


class UnknownModalError(CordlessError):
    """Raised when a modal submission has no registered handler."""


class PermissionDeniedError(CordlessError):
    """Raised by a guard function when the interaction is not permitted."""


class MessageTooLongError(CordlessError):
    """Raised when outgoing message content exceeds Discord's character limit."""


class MissingTokenError(CordlessError):
    """Raised when a bot-token REST call has no token: nothing passed and no
    DISCORD_BOT_TOKEN in the environment."""


class DiscordHTTPError(CordlessError):
    """Raised when Discord's REST API returns a status cordless doesn't
    retry on its own. status/body/headers carry the raw response, so a
    caller that needs more than the message (a header, the raw body) still
    has it, rather than having to parse the message string back apart."""

    def __init__(
        self,
        status: int,
        message: str,
        *,
        body: bytes | None = None,
        headers: Mapping[str, str] | email.message.Message | None = None,
    ) -> None:
        super().__init__(f"Discord API error {status}: {message}")
        self.status = status
        self.body = body
        self.headers = headers


class BadRequest(DiscordHTTPError):
    """400: the request itself was malformed, see the message for which field."""


class Unauthorized(DiscordHTTPError):
    """401: the bot token is missing or invalid."""


class Forbidden(DiscordHTTPError):
    """403: the bot lacks permission for this action."""


class NotFound(DiscordHTTPError):
    """404: the target resource doesn't exist, or the bot can't see it."""


class ServerError(DiscordHTTPError):
    """5xx: Discord's own error, generally safe to retry later."""


_STATUS_ERRORS: dict[int, type[DiscordHTTPError]] = {
    400: BadRequest,
    401: Unauthorized,
    403: Forbidden,
    404: NotFound,
}


def discord_http_error(
    status: int,
    message: str,
    *,
    body: bytes | None = None,
    headers: Mapping[str, str] | email.message.Message | None = None,
) -> DiscordHTTPError:
    """Pick the right DiscordHTTPError subclass for a REST response status:
    one of the named 4xx classes above, ServerError for any 5xx, or the
    base DiscordHTTPError itself for anything else Discord might send."""
    if status in _STATUS_ERRORS:
        cls = _STATUS_ERRORS[status]
    elif status >= 500:
        cls = ServerError
    else:
        cls = DiscordHTTPError
    return cls(status, message, body=body, headers=headers)
