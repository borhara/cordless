"""Single source of truth for cordless's outbound User-Agent header.

Discord sits behind Cloudflare, which blocks urllib's default
"Python-urllib/x.y" User-Agent outright (403, error code 1010) regardless of
whether the credentials are valid - any descriptive User-Agent avoids it.
Matches discord.py's own `DiscordBot ($url, $version)` convention.
"""

from importlib.metadata import version as _version

USER_AGENT = f"DiscordBot (https://github.com/borhara/cordless, {_version('cordless')})"
