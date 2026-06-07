class Responder:
    def send(self, msg):
        return {"statusCode": 200, "body": {"type": 4, "data": {"content": msg}}}

    def edit(self, msg):
        return {"statusCode": 200, "body": {"type": 7, "data": {"content": msg}}}

    def defer(self):
        return {"statusCode": 200, "body": {"type": 5}}
