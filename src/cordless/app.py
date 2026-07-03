import asyncio
import base64
import json

from .context import Context
from .errors import CordlessError
from .register import sync_commands
from .router import Router
from .verify import verify_signature

PING = 1


class Cordless:
    def __init__(self, public_key=None):
        self.router = Router()
        self.public_key = public_key

    def command(self, name, description="No description provided.", options=None, defer=False, dm_permission=True):
        def decorator(func):
            if defer:
                func._defer = True
            self.router.register_command(name, func, description=description, options=options, dm_permission=dm_permission)
            return func

        return decorator

    @property
    def worker_handler(self):
        from .worker import make_worker_handler
        return make_worker_handler(self)

    def button(self, custom_id):
        def decorator(func):
            self.router.register_button(custom_id, func)
            return func

        return decorator

    def select(self, custom_id):
        def decorator(func):
            self.router.register_select(custom_id, func)
            return func

        return decorator

    def modal(self, custom_id):
        def decorator(func):
            self.router.register_modal(custom_id, func)
            return func

        return decorator

    def autocomplete(self, cmd_name, option_name):
        def decorator(func):
            self.router.register_autocomplete(cmd_name, option_name, func)
            return func

        return decorator

    def error(self, func):
        self.router.register_error_handler(func)
        return func

    def guard(self, fn):
        def decorator(handler):
            handler._guard = fn
            return handler

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

        ctx = Context(interaction)

        try:
            return asyncio.run(self.router.dispatch(interaction, ctx))
        except CordlessError as exc:
            return _json_response(400, {"error": str(exc)})

    def sync_commands(self, bot_token=None, client_id=None, client_secret=None, guild_id=None):
        """Push this bot's registered commands to Discord.

        Authenticate with a bot token, or with client_id + client_secret via
        OAuth2 client credentials (no bot user required). Omit `guild_id`
        (the default) to register commands globally, for every guild that
        has authorized the app and every user in it. Run this from a deploy
        step, not from inside the Lambda handler — it makes blocking network
        calls to Discord's API.
        """
        return sync_commands(
            self.router.command_definitions(),
            guild_id=guild_id,
            bot_token=bot_token,
            client_id=client_id,
            client_secret=client_secret,
        )


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
