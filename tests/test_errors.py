"""errors.py's discord_http_error(): picks the right DiscordHTTPError subclass
for a REST response status, so callers can distinguish 403 from 404 from 500
without parsing the message string."""

import pytest

from cordless.errors import (
    BadRequest,
    DiscordHTTPError,
    Forbidden,
    NotFound,
    ServerError,
    Unauthorized,
    discord_http_error,
)


@pytest.mark.parametrize(
    "status,expected",
    [
        (400, BadRequest),
        (401, Unauthorized),
        (403, Forbidden),
        (404, NotFound),
        (500, ServerError),
        (503, ServerError),
        (429, DiscordHTTPError),
        (418, DiscordHTTPError),
    ],
)
def test_discord_http_error_picks_the_right_class(status, expected):
    exc = discord_http_error(status, "message")
    assert type(exc) is expected
    assert isinstance(exc, DiscordHTTPError)


def test_discord_http_error_carries_status_body_and_headers():
    exc = discord_http_error(404, "Unknown Webhook", body=b'{"message": "Unknown Webhook"}', headers={"x": "y"})

    assert exc.status == 404
    assert exc.body == b'{"message": "Unknown Webhook"}'
    assert exc.headers == {"x": "y"}
    assert str(exc) == "Discord API error 404: Unknown Webhook"
