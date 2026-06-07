class Router:
    def __init__(self):
        self.commands = {}
        self.buttons = {}

    def register_command(self, name, handler):
        self.commands[name] = handler

    def register_button(self, custom_id, handler):
        self.buttons[custom_id] = handler

    async def dispatch(self, interaction, ctx):
        itype = interaction["type"]

        # Slash command
        if itype == 2:
            name = interaction["data"]["name"]
            handler = self.commands.get(name)

            if not handler:
                raise Exception(f"Unknown command: {name}")

            return await handler(ctx)

        # Button
        if itype == 3:
            cid = interaction["data"]["custom_id"]
            handler = self.buttons.get(cid)

            if not handler:
                raise Exception(f"Unknown button: {cid}")

            return await handler(ctx)

        raise Exception(f"Unsupported interaction type: {itype}")
