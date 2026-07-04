import json

from nacl.signing import SigningKey

from cordless.app import Cordless


def _signed_event(signing_key, body, timestamp="1234567890"):
    signature = signing_key.sign(f"{timestamp}{body}".encode()).signature.hex()
    return {
        "headers": {
            "X-Signature-Ed25519": signature,
            "X-Signature-Timestamp": timestamp,
        },
        "body": body,
    }


def test_ping_interaction_is_answered_without_a_handler():
    signing_key = SigningKey.generate()
    public_key = signing_key.verify_key.encode().hex()

    bot = Cordless(public_key=public_key)
    body = json.dumps({"type": 1})

    result = bot.handle(_signed_event(signing_key, body))

    assert result["statusCode"] == 200
    assert json.loads(result["body"])["type"] == 1


def test_valid_signature_is_accepted():
    signing_key = SigningKey.generate()
    public_key = signing_key.verify_key.encode().hex()

    bot = Cordless(public_key=public_key)

    @bot.command("ping")
    async def ping(ctx):
        return await ctx.send("pong")

    body = json.dumps({"type": 2, "data": {"name": "ping"}})

    result = bot.handle(_signed_event(signing_key, body))

    assert result["statusCode"] == 200


def test_invalid_signature_is_rejected():
    signing_key = SigningKey.generate()
    public_key = signing_key.verify_key.encode().hex()

    bot = Cordless(public_key=public_key)
    body = json.dumps({"type": 1})

    event = {
        "headers": {
            "X-Signature-Ed25519": "00" * 64,
            "X-Signature-Timestamp": "1234567890",
        },
        "body": body,
    }

    result = bot.handle(event)

    assert result["statusCode"] == 401


def test_missing_signature_headers_are_rejected():
    signing_key = SigningKey.generate()
    public_key = signing_key.verify_key.encode().hex()

    bot = Cordless(public_key=public_key)

    result = bot.handle({"body": json.dumps({"type": 1})})

    assert result["statusCode"] == 401


def test_base64_encoded_body_is_decoded_before_verification():
    import base64

    signing_key = SigningKey.generate()
    public_key = signing_key.verify_key.encode().hex()

    bot = Cordless(public_key=public_key)
    body = json.dumps({"type": 1})
    timestamp = "1234567890"
    signature = signing_key.sign(f"{timestamp}{body}".encode()).signature.hex()

    event = {
        "headers": {
            "X-Signature-Ed25519": signature,
            "X-Signature-Timestamp": timestamp,
        },
        "body": base64.b64encode(body.encode()).decode(),
        "isBase64Encoded": True,
    }

    result = bot.handle(event)

    assert result["statusCode"] == 200


def test_pure_python_fallback_accepts_valid_signature(monkeypatch):
    import cordless.verify
    monkeypatch.setattr(cordless.verify, "VerifyKey", None)

    signing_key = SigningKey.generate()
    public_key = signing_key.verify_key.encode().hex()

    bot = Cordless(public_key=public_key)
    body = json.dumps({"type": 1})

    result = bot.handle(_signed_event(signing_key, body))
    assert result["statusCode"] == 200


def test_pure_python_fallback_rejects_invalid_signature(monkeypatch):
    import cordless.verify
    monkeypatch.setattr(cordless.verify, "VerifyKey", None)

    signing_key = SigningKey.generate()
    public_key = signing_key.verify_key.encode().hex()

    bot = Cordless(public_key=public_key)
    event = {
        "headers": {
            "X-Signature-Ed25519": "00" * 64,
            "X-Signature-Timestamp": "1234567890",
        },
        "body": json.dumps({"type": 1}),
    }

    result = bot.handle(event)
    assert result["statusCode"] == 401


def test_nacl_fast_path_is_active_when_installed():
    import cordless.verify
    assert cordless.verify.VerifyKey is not None  # pynacl is a dev dep, fast path must be wired


def test_no_public_key_skips_verification():
    bot = Cordless()

    @bot.command("ping")
    async def ping(ctx):
        return await ctx.send("pong")

    result = bot.handle({"body": json.dumps({"type": 2, "data": {"name": "ping"}})})

    assert result["statusCode"] == 200
