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
