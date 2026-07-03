from .errors import NoResponseError, UnknownButtonError, UnknownCommandError, UnsupportedInteractionError

PING = 1
APPLICATION_COMMAND = 2
MESSAGE_COMPONENT = 3


class Router:
    def __init__(self):
        self.commands = {}
        self.buttons = {}

    def register_command(self, name, handler, description="No description provided.", options=None):
        self.commands[name] = {
            "handler": handler,
            "description": description,
            "options": options or [],
        }

    def register_button(self, custom_id, handler):
        self.buttons[custom_id] = handler

    def command_definitions(self):
        return [
            {
                "name": name,
                "description": meta["description"],
                "type": 1,
                "options": meta["options"],
            }
            for name, meta in self.commands.items()
        ]

    async def dispatch(self, interaction, ctx):
        itype = interaction["type"]

        if itype == APPLICATION_COMMAND:
            name = interaction["data"]["name"]
            entry = self.commands.get(name)

            if not entry:
                raise UnknownCommandError(f"Unknown command: {name}")

            return await _invoke(entry["handler"], ctx, f"Command '{name}'")

        if itype == MESSAGE_COMPONENT:
            cid = interaction["data"]["custom_id"]
            handler = self.buttons.get(cid)

            if not handler:
                raise UnknownButtonError(f"Unknown button: {cid}")

            return await _invoke(handler, ctx, f"Button '{cid}'")

        raise UnsupportedInteractionError(f"Unsupported interaction type: {itype}")


async def _invoke(handler, ctx, description):
    result = await handler(ctx)
    response = result if result is not None else ctx.response

    if response is None:
        raise NoResponseError(f"{description} handler never called ctx.send/edit/defer nor returned a response")

    return response
