import json
import asyncio

from .router import Router
from .context import Context
from .response.responder import Responder


class Cordless:
    def __init__(self):
        self.router = Router()

    def command(self, name):
        def decorator(func):
            self.router.register_command(name, func)
            return func

        return decorator

    def handle(self, event):
        interaction = json.loads(event["body"])

        responder = Responder()
        ctx = Context(interaction, responder)

        return asyncio.run(self.router.dispatch(interaction, ctx))
