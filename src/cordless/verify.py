import hashlib

# PyNaCl verifies in C at ~100x the speed of the pure-Python fallback below,
# worth real milliseconds inside Discord's 3-second window on small Lambdas.
# Opt in by adding "pynacl" to packages in cordless.toml.
try:
    from nacl.exceptions import BadSignatureError
    from nacl.signing import VerifyKey
except ImportError:
    VerifyKey = None

# Ed25519 curve parameters (RFC 8032)
_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_SQRTN1 = pow(2, (_P - 1) // 4, _P)
# Base point compressed (y = 4/5 mod p, x positive), little-endian
_B_BYTES = bytes.fromhex("5866666666666666666666666666666666666666666666666666666666666666")


def _point_add(P, Q):
    x1, y1, z1, t1 = P
    x2, y2, z2, t2 = Q
    a = (y1 - x1) * (y2 - x2) % _P
    b = (y1 + x1) * (y2 + x2) % _P
    c = 2 * t1 * t2 * _D % _P
    d = 2 * z1 * z2 % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return e * f % _P, g * h % _P, f * g % _P, e * h % _P


def _point_mul(s, P):
    R = (0, 1, 1, 0)  # identity point in extended coordinates
    while s > 0:
        if s & 1:
            R = _point_add(R, P)
        P = _point_add(P, P)
        s >>= 1
    return R


def _point_decompress(b):
    if len(b) != 32:
        raise ValueError("invalid point length")
    y = int.from_bytes(b, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    y2 = y * y % _P
    x2 = (y2 - 1) * pow(_D * y2 + 1, _P - 2, _P) % _P
    if x2 == 0:
        if sign:
            raise ValueError("invalid point")
        return (0, y, 1, 0)
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRTN1 % _P
    if (x * x - x2) % _P != 0:
        raise ValueError("invalid point")
    if x % 2 != sign:
        x = _P - x
    return (x, y, 1, x * y % _P)


def _point_equal(P, Q):
    return (P[0] * Q[2] - Q[0] * P[2]) % _P == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _P == 0


_B = _point_decompress(_B_BYTES)


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

    if VerifyKey is not None:
        try:
            VerifyKey(pk_bytes).verify(f"{timestamp}{body}".encode(), sig_bytes)
            return True
        except (BadSignatureError, ValueError):
            return False

    try:
        A = _point_decompress(pk_bytes)
        R = _point_decompress(sig_bytes[:32])
    except ValueError:
        return False

    S = int.from_bytes(sig_bytes[32:], "little")
    if S >= _L:
        return False

    message = f"{timestamp}{body}".encode()
    h = int.from_bytes(hashlib.sha512(sig_bytes[:32] + pk_bytes + message).digest(), "little") % _L

    return _point_equal(_point_mul(S, _B), _point_add(R, _point_mul(h, A)))
