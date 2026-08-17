from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey


def verify_signature(public_key, signature, timestamp, body):
    """Verify a Discord interaction request using Ed25519.

    See: https://discord.com/developers/docs/interactions/receiving-and-responding#security-and-authorization
    """
    if not public_key or not signature or not timestamp:
        return False

    try:
        pk_bytes = bytes.fromhex(public_key)
        sig_bytes = bytes.fromhex(signature)
    except ValueError:
        return False

    if len(pk_bytes) != 32 or len(sig_bytes) != 64:
        return False

    try:
        VerifyKey(pk_bytes).verify(f"{timestamp}{body}".encode(), sig_bytes)
        return True
    except (BadSignatureError, ValueError):
        return False
