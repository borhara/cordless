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
    from .deploy import load_config
    toml_env = load_config(os.getcwd()).get("env", {})

    token = args.token
    client_id = args.client_id or toml_env.get("DISCORD_CLIENT_ID")
    client_secret = args.client_secret

    if not token and not (client_id and client_secret):
        raise SystemExit(
            "Credentials required: pass --token (or set $DISCORD_BOT_TOKEN), "
            "or both --client-id/--client-secret (or $DISCORD_CLIENT_ID/$DISCORD_CLIENT_SECRET)"
        )

    bot = _load_bot(args.bot)
    commands = bot.sync_commands(
        bot_token=token,
        client_id=client_id,
        client_secret=client_secret,
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
    defer_worker = args.defer_worker or cfg.get("defer_worker")
    deploy(
        function_name=function_name,
        role_name=args.role_name or cfg.get("role_name") or f"{function_name}-role",
        handler=args.handler or cfg.get("handler", "lambda_function.handler"),
        source_dir=source_dir,
        runtime=args.runtime or cfg.get("runtime", "python3.12"),
        layer_name=args.layer_name or cfg.get("layer_name", "cordless"),
        env={**cfg.get("env", {}), **env},
        region=args.region or cfg.get("region") or os.environ.get("AWS_DEFAULT_REGION"),
        timeout=int(args.timeout or cfg.get("timeout", 10)),
        bundle_cordless=args.bundle_cordless or cfg.get("bundle_cordless", False),
        defer_worker=defer_worker,
        defer_handler=args.defer_handler or cfg.get("defer_handler", "lambda_function.worker_handler"),
        defer_timeout=int(args.defer_timeout or cfg.get("defer_timeout", 30)),
    )


def _logs(args):
    import time
    from ._aws import get_session
    from .deploy import load_config

    region = args.region or load_config(os.getcwd()).get("region")
    if not region:
        raise SystemExit(
            "Region is required. Pass --region, set AWS_DEFAULT_REGION, "
            "or add `region` to [deploy] in cordless.toml."
        )

    session = get_session(region)
    cw = session.client("logs")
    log_group = f"/aws/lambda/{args.function}"
    start_ms = int((time.time() - args.since * 60) * 1000)
    seen = set()

    def fetch_and_print(since_ms):
        latest = since_ms
        kwargs = {"logGroupName": log_group, "startTime": since_ms, "interleaved": True}
        while True:
            try:
                resp = cw.filter_log_events(**kwargs)
            except cw.exceptions.ResourceNotFoundException:
                raise SystemExit(
                    f"Log group not found: {log_group}\n"
                    "Has the function been invoked at least once?"
                )
            for e in resp.get("events", []):
                eid = e["eventId"]
                if eid not in seen:
                    seen.add(eid)
                    ts = time.strftime("%H:%M:%S", time.localtime(e["timestamp"] / 1000))
                    print(f"  {ts}  {e['message'].rstrip()}")
                    latest = max(latest, e["timestamp"])
            token = resp.get("nextToken")
            if not token:
                break
            kwargs["nextToken"] = token
        return latest

    latest_ms = fetch_and_print(start_ms)
    if args.follow:
        print("  --- following (Ctrl+C to stop) ---", flush=True)
        try:
            while True:
                time.sleep(2)
                latest_ms = fetch_and_print(latest_ms + 1)
        except KeyboardInterrupt:
            print()


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
    deploy_cmd.add_argument("--timeout", metavar="SECONDS", default=None, help="Main Lambda timeout in seconds (default: 10)")
    deploy_cmd.add_argument("--bundle-cordless", action="store_true", default=False, help="Embed local cordless source in the zip instead of using a Lambda layer")
    deploy_cmd.add_argument("--defer-worker", metavar="NAME", help="Name of the worker Lambda for deferred commands (also set via cordless.toml defer_worker)")
    deploy_cmd.add_argument("--defer-handler", metavar="HANDLER", default=None, help="Worker handler string (default: lambda_function.worker_handler)")
    deploy_cmd.add_argument("--defer-timeout", metavar="SECONDS", default=None, help="Worker Lambda timeout in seconds (default: 30)")
    deploy_cmd.set_defaults(func=_deploy)

    # logs
    logs_cmd = subparsers.add_parser("logs", help="Tail CloudWatch logs for a deployed Lambda function")
    logs_cmd.add_argument("--function", "-f", required=True, metavar="FUNCTION", help="Lambda function name")
    logs_cmd.add_argument("--region", "-r", default=os.environ.get("AWS_DEFAULT_REGION"), metavar="REGION", help="AWS region")
    logs_cmd.add_argument("--follow", action="store_true", help="Keep tailing (Ctrl+C to stop)")
    logs_cmd.add_argument("--since", type=int, default=10, metavar="MINUTES", help="How many minutes back to start (default: 10)")
    logs_cmd.set_defaults(func=_logs)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
