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
    if not args.token and not (args.client_id and args.client_secret):
        raise SystemExit(
            "Credentials required: pass --token (or set $DISCORD_BOT_TOKEN), "
            "or both --client-id/--client-secret (or $DISCORD_CLIENT_ID/$DISCORD_CLIENT_SECRET)"
        )

    bot = _load_bot(args.bot)
    commands = bot.sync_commands(
        bot_token=args.token,
        client_id=args.client_id,
        client_secret=args.client_secret,
        guild_id=args.guild_id,
    )

    scope = f"guild {args.guild_id}" if args.guild_id else "globally"
    names = ", ".join(c["name"] for c in commands) or "(none)"
    print(f"Registered {len(commands)} command(s) {scope}: {names}")


def _upload(args):
    from .upload import upload
    upload(
        function_name=args.function,
        layer_name=args.layer_name,
        region=args.region,
    )


def _deploy(args):
    from .deploy import deploy, load_config

    source_dir = os.path.abspath(args.source)
    cfg = load_config(source_dir)

    env = {}
    for pair in (args.env or []):
        if "=" not in pair:
            raise SystemExit(f"--env values must be KEY=VALUE, got: {pair!r}")
        k, _, v = pair.partition("=")
        env[k] = v

    function_name = args.function or cfg.get("function")
    deploy(
        function_name=function_name,
        role_name=args.role_name or cfg.get("role_name") or f"{function_name}-role",
        handler=args.handler or cfg.get("handler", "lambda_function.handler"),
        source_dir=source_dir,
        runtime=args.runtime or cfg.get("runtime", "python3.12"),
        layer_name=args.layer_name or cfg.get("layer_name", "cordless"),
        env={**cfg.get("env", {}), **env},
        region=args.region or cfg.get("region") or os.environ.get("AWS_DEFAULT_REGION"),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cordless", description="cordless command-line tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # register
    register = subparsers.add_parser("register", help="Register this bot's slash commands with Discord")
    register.add_argument("bot", help="Location of your Cordless instance, as MODULE:ATTRIBUTE (e.g. app:bot)")
    register.add_argument("--token", default=os.environ.get("DISCORD_BOT_TOKEN"), help="Bot token (defaults to $DISCORD_BOT_TOKEN)")
    register.add_argument("--client-id", default=os.environ.get("DISCORD_CLIENT_ID"), help="App client id (defaults to $DISCORD_CLIENT_ID)")
    register.add_argument("--client-secret", default=os.environ.get("DISCORD_CLIENT_SECRET"), help="App client secret (defaults to $DISCORD_CLIENT_SECRET)")
    register.add_argument("--guild-id", default=os.environ.get("DISCORD_GUILD_ID"), help="Register to a single guild (defaults to $DISCORD_GUILD_ID)")
    register.set_defaults(func=_register)

    # upload
    upload = subparsers.add_parser("upload", help="Package cordless as a Lambda layer and attach it to your function")
    upload.add_argument("--function", "-f", required=True, metavar="FUNCTION", help="Lambda function name or ARN")
    upload.add_argument("--layer-name", default="cordless", metavar="NAME", help="Layer name (default: cordless)")
    upload.add_argument("--region", "-r", default=os.environ.get("AWS_DEFAULT_REGION"), metavar="REGION", help="AWS region")
    upload.set_defaults(func=_upload)

    # deploy
    deploy_cmd = subparsers.add_parser(
        "deploy",
        help="Package and deploy your bot to Lambda with the cordless layer attached",
    )
    deploy_cmd.add_argument("--function", "-f", metavar="FUNCTION", help="Lambda function name")
    deploy_cmd.add_argument("--role-name", metavar="NAME", help="IAM role name to create or reuse (default: <function>-role)")
    deploy_cmd.add_argument("--handler", metavar="HANDLER", help="Handler string, e.g. lambda_function.handler (default: lambda_function.handler)")
    deploy_cmd.add_argument("--source", "-s", default=".", metavar="DIR", help="Source directory to package (default: current directory)")
    deploy_cmd.add_argument("--runtime", metavar="RUNTIME", help="Lambda runtime (default: python3.12)")
    deploy_cmd.add_argument("--layer-name", default=None, metavar="NAME", help="Cordless layer name (default: cordless)")
    deploy_cmd.add_argument("--region", "-r", default=None, metavar="REGION", help="AWS region")
    deploy_cmd.add_argument("--env", metavar="KEY=VALUE", action="append", help="Environment variable (repeatable)")
    deploy_cmd.set_defaults(func=_deploy)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
