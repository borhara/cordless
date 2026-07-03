import argparse
import importlib
import os
import sys


def _load_bot(target):
    module_name, _, attr = target.partition(":")

    if not attr:
        raise SystemExit(f"Expected MODULE:ATTRIBUTE (e.g. app:bot), got: {target}")

    sys.path.insert(0, os.getcwd())
    module = importlib.import_module(module_name)

    try:
        return getattr(module, attr)
    except AttributeError:
        raise SystemExit(f"Module '{module_name}' has no attribute '{attr}'")


def _register(args):
    if not args.token:
        raise SystemExit("A bot token is required: pass --token or set DISCORD_BOT_TOKEN")

    bot = _load_bot(args.bot)
    commands = bot.sync_commands(bot_token=args.token, guild_id=args.guild_id)

    scope = f"guild {args.guild_id}" if args.guild_id else "globally"
    names = ", ".join(c["name"] for c in commands) or "(none)"
    print(f"Registered {len(commands)} command(s) {scope}: {names}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cordless", description="cordless command-line tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register = subparsers.add_parser("register", help="Register this bot's slash commands with Discord")
    register.add_argument("bot", help="Location of your Cordless instance, as MODULE:ATTRIBUTE (e.g. app:bot)")
    register.add_argument(
        "--token", default=os.environ.get("DISCORD_BOT_TOKEN"), help="Bot token (defaults to $DISCORD_BOT_TOKEN)"
    )
    register.add_argument(
        "--guild-id",
        default=os.environ.get("DISCORD_GUILD_ID"),
        help="Register to a single guild instead of globally (defaults to $DISCORD_GUILD_ID)",
    )
    register.set_defaults(func=_register)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
