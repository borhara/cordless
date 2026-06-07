import asyncio
from .router import Router


class Cordless:
    def __init__(self):
        self.router = Router()

    # -------------------
    # decorators
    # -------------------
    def command(self, name):
        def decorator(func):
            self.router.register_command(name, func)
            return func

        return decorator

    def button(self, custom_id):
        def decorator(func):
            self.router.register_button(custom_id, func)
            return func

        return decorator

    # -------------------
    # entrypoint (Lambda / HTTP)
    # -------------------
    def handle(self, event):
        interaction = self._parse(event)
        ctx = self._make_ctx(interaction)

        return asyncio.run(self.router.dispatch(interaction, ctx))

    # -------------------
    # internal helpers (temporary here)
    # -------------------
    def _parse(self, event):
        import json

        return json.loads(event["body"])

    def _make_ctx(self, interaction):
        class Context:
            async def send(self, msg):
                return {
                    "statusCode": 200,
                    "body": {"type": 4, "data": {"content": msg}},
                }

        return Context()
