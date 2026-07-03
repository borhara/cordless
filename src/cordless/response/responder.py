import json

CHANNEL_MESSAGE_WITH_SOURCE = 4
UPDATE_MESSAGE = 7
DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5


class Responder:
    def send(self, msg):
        return _response({"type": CHANNEL_MESSAGE_WITH_SOURCE, "data": {"content": msg}})

    def edit(self, msg):
        return _response({"type": UPDATE_MESSAGE, "data": {"content": msg}})

    def defer(self):
        return _response({"type": DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE})


def _response(payload):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }
