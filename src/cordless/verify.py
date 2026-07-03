from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey


def verify_signature(public_key, signature, timestamp, body):
    """Verify a Discord interaction request using Ed25519.

    See: https://discord.com/developers/docs/interactions/receiving-and-responding#security-and-authorization
    """
    if not public_key or not signature or not timestamp:
        return False

    try:
        verify_key = VerifyKey(bytes.fromhex(public_key))
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError):
        return False
