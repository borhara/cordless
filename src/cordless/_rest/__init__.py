"""Internal REST resource modules backing Cordless's flat bot.<verb>_<resource>()
surface and the matching action methods on model objects (Guild, Channel,
Thread, ...).

Not a public import path - everything here is reached through a Cordless
instance (see _mixin.py) or through a model object returned from one, the
same way _aws.py/_multipart.py are internal.
"""
