# pyright: strict
"""Internal REST resource modules backing Cordless's flat
bot.<verb>_<resource>() API and the corresponding action methods on model
objects such as Guild, Channel, and Thread.

This is not a public import path. REST resources are accessed through a
Cordless instance via _mixin.py or through model objects returned by those
methods, following the same internal-module pattern used by _aws.py and
_multipart.py.
"""
