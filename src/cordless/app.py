import asyncio
import base64
import json

from .context import Context
from .errors import CordlessError
from .register import sync_commands
from .response.responder import Responder
from .router import Router
from .verify import verify_signature

PING = 1


class Cordless:
    def __init__(self, public_key=None):
        self.router = Router()
        self.public_key = public_key

    def command(self, name, description="No description provided.", options=None):
        def decorator(func):
            self.router.register_command(name, func, description=description, options=options)
            return func

        return decorator

    def button(self, custom_id):
        def decorator(func):
            self.router.register_button(custom_id, func)
            return func

        return decorator

    def handle(self, event, context=None):
        body = _extract_body(event)

        if self.public_key:
            headers = event.get("headers") or {}
            signature = _get_header(headers, "x-signature-ed25519")
            timestamp = _get_header(headers, "x-signature-timestamp")

            if not verify_signature(self.public_key, signature, timestamp, body):
                return _json_response(401, {"error": "invalid request signature"})

        interaction = json.loads(body)

        if interaction.get("type") == PING:
            return _json_response(200, {"type": PING})

        responder = Responder()
        ctx = Context(interaction, responder)

        try:
            return asyncio.run(self.router.dispatch(interaction, ctx))
        except CordlessError as exc:
            return _json_response(400, {"error": str(exc)})

    def sync_commands(self, application_id, bot_token, guild_id=None):
        """Push this bot's registered commands to Discord.

        Run this from a deploy step, not from inside the Lambda handler —
        it makes a blocking network call to Discord's API.
        """
        return sync_commands(application_id, bot_token, self.router.command_definitions(), guild_id=guild_id)


def _extract_body(event):
    body = event.get("body", "")

    if event.get("isBase64Encoded"):
        return base64.b64decode(body).decode()

    return body


def _get_header(headers, name):
    name = name.lower()

    for key, value in headers.items():
        if key.lower() == name:
            return value

    return None


def _json_response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }
