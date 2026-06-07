class Context:
    def __init__(self, interaction, responder):
        self.interaction = interaction
        self.responder = responder

    async def send(self, msg):
        return self.responder.send(msg)

    async def edit(self, msg):
        return self.responder.edit(msg)

    async def defer(self):
        return self.responder.defer()
