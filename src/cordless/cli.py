import argparse
import importlib
import os
import sys


def _load_bot(target, path=None):
    module_name, _, attr = target.partition(":")

    if not attr:
        raise SystemExit(f"Expected MODULE:ATTRIBUTE (e.g. app:bot), got: {target}")

    sys.path.insert(0, path or os.getcwd())
    module = importlib.import_module(module_name)

    try:
        return getattr(module, attr)
    except AttributeError:
        raise SystemExit(f"Module '{module_name}' has no attribute '{attr}'")


def _pick(*values):
    """First value that is not None, so 0 and "" survive (unlike `or`)."""
    for v in values:
        if v is not None:
            return v
    return None


def _detect_bot_target(source_dir):
    """Scan source_dir for a Cordless() assignment; returns 'module:attr' or None."""
    import ast

    try:
        files = os.listdir(source_dir)
    except OSError:
        return None

    # lambda_function.py first (conventional entry point), then other root-level .py files
    candidates = []
    if "lambda_function.py" in files:
        candidates.append("lambda_function.py")
    candidates.extend(
        f for f in sorted(files)
        if f.endswith(".py")
        and f != "lambda_function.py"
        and not f.startswith("_")
        and not f.startswith("test_")
    )

    for filename in candidates:
        try:
            with open(os.path.join(source_dir, filename)) as fh:
                tree = ast.parse(fh.read(), filename)
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "Cordless"
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        return f"{filename[:-3]}:{target.id}"
    return None


def _resolve_bot(explicit, source_dir, cfg=None):
    """Resolve bot target: explicit arg → cordless.toml → AST scan."""
    if explicit:
        return explicit
    if cfg is not None and cfg.get("bot"):
        return cfg["bot"]
    return _detect_bot_target(source_dir)


def _register(args):
    from .deploy import load_config

    source_dir = os.getcwd()
    cfg = load_config(source_dir)
    toml_env = cfg.get("env", {})

    token = args.token
    client_id = args.client_id or toml_env.get("DISCORD_CLIENT_ID")
    client_secret = args.client_secret or toml_env.get("DISCORD_CLIENT_SECRET")

    if not token and not (client_id and client_secret):
        raise SystemExit(
            "Credentials required: pass --token (or set $DISCORD_BOT_TOKEN), "
            "or both --client-id/--client-secret (or $DISCORD_CLIENT_ID/$DISCORD_CLIENT_SECRET)"
        )

    target = _resolve_bot(args.bot, source_dir, cfg)
    if not target:
        raise SystemExit(
            "Bot location required: pass it as an argument (e.g. `cordless register lambda_function:bot`) "
            "or add `bot` to [deploy] in cordless.toml."
        )

    bot = _load_bot(target, path=source_dir)
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
        python_version=args.runtime.replace("python", ""),
    )


def _deploy(args):
    from .deploy import deploy, load_config

    source_dir = os.path.abspath(args.source)
    cfg = load_config(source_dir)

    setup_target = args.setup or cfg.get("setup")
    if setup_target:
        print(f"  running setup {setup_target}...")
        sys.path.insert(0, source_dir)
        setup_fn = _load_bot(setup_target)
        setup_fn()
        print(f"  ✓ setup")

    env = {}
    for pair in (args.env or []):
        if "=" not in pair:
            raise SystemExit(f"--env values must be KEY=VALUE, got: {pair!r}")
        k, _, v = pair.partition("=")
        env[k] = v

    function_name = args.function or cfg.get("function")
    runtime = args.runtime or cfg.get("runtime", "python3.12")
    defer_worker = args.defer_worker or cfg.get("defer_worker")

    # Loading the bot is only needed for cron schedules and --register;
    # resolved from toml or auto-detected from source files.
    bot_target = _resolve_bot(None, source_dir, cfg)
    bot = _load_bot(bot_target, path=source_dir) if bot_target else None
    crons = {name: entry["schedule"] for name, entry in bot.crons.items()} if bot else None

    deploy(
        function_name=function_name,
        role_name=args.role_name or cfg.get("role_name") or f"{function_name}-role",
        handler=args.handler or cfg.get("handler", "lambda_function.handler"),
        source_dir=source_dir,
        runtime=runtime,
        layer_name=args.layer_name or cfg.get("layer_name", "cordless"),
        env={**cfg.get("env", {}), **env},
        region=args.region or cfg.get("region") or os.environ.get("AWS_DEFAULT_REGION"),
        timeout=int(_pick(args.timeout, cfg.get("timeout"), 10)),
        memory=int(cfg.get("memory", 256)),
        bundle_cordless=args.bundle_cordless or cfg.get("bundle_cordless", False),
        packages=cfg.get("packages"),
        python_version=runtime.replace("python", ""),
        defer_worker=defer_worker,
        defer_handler=args.defer_handler or cfg.get("defer_handler", "lambda_function.worker_handler"),
        defer_timeout=int(_pick(args.defer_timeout, cfg.get("defer_timeout"), 30)),
        defer_memory=int(cfg.get("defer_memory", 256)),
        policies=cfg.get("policies"),
        crons=crons,
    )

    if args.register:
        if not bot:
            raise SystemExit(
                "--register: could not find a Cordless() instance. "
                "Add `bot` to [deploy] in cordless.toml or ensure lambda_function.py contains a Cordless() instance."
            )
        toml_env = cfg.get("env", {})
        token = os.environ.get("DISCORD_BOT_TOKEN")
        client_id = os.environ.get("DISCORD_CLIENT_ID") or toml_env.get("DISCORD_CLIENT_ID")
        client_secret = os.environ.get("DISCORD_CLIENT_SECRET") or toml_env.get("DISCORD_CLIENT_SECRET")
        if not token and not (client_id and client_secret):
            raise SystemExit(
                "--register requires $DISCORD_BOT_TOKEN, "
                "or both $DISCORD_CLIENT_ID and $DISCORD_CLIENT_SECRET"
            )
        commands = bot.sync_commands(
            bot_token=token,
            client_id=client_id,
            client_secret=client_secret,
        )
        names = ", ".join(c["name"] for c in commands) or "(none)"
        print(f"  ✓ registered {len(commands)} command(s): {names}")


def _destroy(args):
    from .deploy import destroy, load_config

    cfg = load_config(os.getcwd())
    function_name = args.function or cfg.get("function")
    if not function_name:
        raise SystemExit("Function name required: pass --function or add `function` to [deploy] in cordless.toml.")
    role_name = args.role_name or cfg.get("role_name") or f"{function_name}-role"
    region = args.region or cfg.get("region") or os.environ.get("AWS_DEFAULT_REGION")
    defer_worker = args.defer_worker or cfg.get("defer_worker")

    if not args.yes:
        targets = f"function '{function_name}'" + (f", worker '{defer_worker}'" if defer_worker else "")
        answer = input(f"Delete {targets}, its API Gateway, logs, and role '{role_name}'? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            raise SystemExit("Aborted.")

    destroy(function_name=function_name, role_name=role_name, region=region, defer_worker=defer_worker)


_INIT_LAMBDA = '''\
import os

from cordless import Cordless

bot = Cordless(public_key=os.environ.get("DISCORD_PUBLIC_KEY"))


@bot.command("ping", description="Check the bot is alive")
async def ping(ctx):
    await ctx.send("pong")


handler = bot.handler()
'''

_INIT_TOML = '''\
[deploy]
function = "{name}"
# region = "eu-west-2"

[deploy.env]
DISCORD_PUBLIC_KEY = ""
'''

_INIT_ENV = '''\
# Discord Developer Portal -> your app -> General Information
DISCORD_PUBLIC_KEY=
DISCORD_CLIENT_ID=
DISCORD_BOT_TOKEN=
'''


def _init(args):
    name = args.name or os.path.basename(os.getcwd())
    files = {
        "lambda_function.py": _INIT_LAMBDA,
        "cordless.toml": _INIT_TOML.format(name=name),
        ".env.example": _INIT_ENV,
    }
    for fname, content in files.items():
        if os.path.exists(fname):
            print(f"  - {fname} already exists, skipped")
            continue
        with open(fname, "w") as f:
            f.write(content)
        print(f"  ✓ {fname}")
    print(f"\nNext: fill in DISCORD_PUBLIC_KEY in cordless.toml, then run `cordless deploy`")


def _dev(args):
    from .deploy import load_config
    from .dev import run_dev

    source_dir = os.path.abspath(args.source)
    cfg = load_config(source_dir)
    target = _resolve_bot(args.bot, source_dir, cfg)
    if not target:
        raise SystemExit(
            "Bot location required: pass it as an argument (e.g. `cordless dev lambda_function:bot`) "
            "or add `bot` to [deploy] in cordless.toml."
        )
    run_dev(target, port=args.port, tunnel=not args.no_tunnel, source_dir=source_dir)


def _logs(args):
    import time
    from ._aws import get_session
    from .deploy import load_config

    cfg = load_config(os.getcwd())
    function = args.function or cfg.get("function")
    if not function:
        raise SystemExit("Function name required: pass --function or add `function` to [deploy] in cordless.toml.")
    region = args.region or cfg.get("region")
    if not region:
        raise SystemExit(
            "Region is required. Pass --region, set AWS_DEFAULT_REGION, "
            "or add `region` to [deploy] in cordless.toml."
        )

    # skip the STS validation round-trip, a credentials problem surfaces
    # on the first CloudWatch call anyway
    session = get_session(region, validate=False)
    cw = session.client("logs")
    log_group = f"/aws/lambda/{function}"
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

    try:
        from botocore.exceptions import NoCredentialsError
    except ImportError:
        raise SystemExit("boto3 is required for logs.\nInstall it: pip install 'cordless[deploy]'")
    try:
        latest_ms = fetch_and_print(start_ms)
    except NoCredentialsError:
        from ._aws import _NO_CREDENTIALS_MSG
        raise SystemExit(_NO_CREDENTIALS_MSG)
    if args.follow:
        print("  --- following (Ctrl+C to stop) ---", flush=True)
        try:
            while True:
                time.sleep(2)
                latest_ms = fetch_and_print(latest_ms + 1)
        except KeyboardInterrupt:
            print()


def _load_env(source_dir):
    """Load .env and cordless.toml [deploy.env] into the environment (no clobber)."""
    env_path = os.path.join(source_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def main(argv=None):
    _load_env(os.getcwd())
    parser = argparse.ArgumentParser(prog="cordless", description="cordless command-line tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # register
    register = subparsers.add_parser("register", help="Register this bot's slash commands with Discord")
    register.add_argument("bot", nargs="?", default=None, help="Location of your Cordless instance, as MODULE:ATTRIBUTE (e.g. app:bot); auto-detected if omitted")
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
    upload.add_argument("--runtime", default="python3.12", metavar="RUNTIME", help="Lambda runtime the layer targets (default: python3.12)")
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
    deploy_cmd.add_argument("--setup", metavar="MODULE:FUNCTION", default=None, help="Run a setup function before deploying (e.g. db:create_tables)")
    deploy_cmd.add_argument("--bundle-cordless", action="store_true", default=False, help="Embed local cordless source in the zip instead of using a Lambda layer")
    deploy_cmd.add_argument("--defer-worker", metavar="NAME", help="Name of the worker Lambda for deferred commands (also set via cordless.toml defer_worker)")
    deploy_cmd.add_argument("--defer-handler", metavar="HANDLER", default=None, help="Worker handler string (default: lambda_function.worker_handler)")
    deploy_cmd.add_argument("--defer-timeout", metavar="SECONDS", default=None, help="Worker Lambda timeout in seconds (default: 30)")
    deploy_cmd.add_argument("--register", action="store_true", default=False, help="Register slash commands with Discord after deploy (auto-detects bot; reads credentials from $DISCORD_BOT_TOKEN or $DISCORD_CLIENT_ID/$DISCORD_CLIENT_SECRET)")
    deploy_cmd.set_defaults(func=_deploy)

    # destroy
    destroy_cmd = subparsers.add_parser("destroy", help="Delete the Lambda function(s), API Gateway, cron rules, logs, and IAM role for a deployed bot")
    destroy_cmd.add_argument("--function", "-f", default=None, metavar="FUNCTION", help="Lambda function name (defaults to `function` in cordless.toml)")
    destroy_cmd.add_argument("--role-name", metavar="NAME", default=None, help="IAM role name (default: <function>-role)")
    destroy_cmd.add_argument("--region", "-r", default=None, metavar="REGION", help="AWS region")
    destroy_cmd.add_argument("--defer-worker", metavar="NAME", default=None, help="Worker Lambda to also delete")
    destroy_cmd.add_argument("--yes", "-y", action="store_true", help="Skip the confirmation prompt")
    destroy_cmd.set_defaults(func=_destroy)

    # init
    init_cmd = subparsers.add_parser("init", help="Scaffold a new cordless bot in the current directory")
    init_cmd.add_argument("name", nargs="?", default=None, help="Function name (default: current directory name)")
    init_cmd.set_defaults(func=_init)

    # dev
    dev_cmd = subparsers.add_parser("dev", help="Run your bot locally with hot reload and a public tunnel")
    dev_cmd.add_argument("bot", nargs="?", default=None, help="Your Cordless instance as MODULE:ATTRIBUTE (auto-detected if omitted)")
    dev_cmd.add_argument("--port", "-p", type=int, default=8787, help="Port to listen on (default: 8787)")
    dev_cmd.add_argument("--source", "-s", default=".", metavar="DIR", help="Project directory (default: current directory)")
    dev_cmd.add_argument("--no-tunnel", action="store_true", help="Serve on localhost only, skip cloudflared")
    dev_cmd.set_defaults(func=_dev)

    # logs
    logs_cmd = subparsers.add_parser("logs", help="Tail CloudWatch logs for a deployed Lambda function")
    logs_cmd.add_argument("--function", "-f", default=None, metavar="FUNCTION", help="Lambda function name (defaults to `function` in cordless.toml)")
    logs_cmd.add_argument("--region", "-r", default=os.environ.get("AWS_DEFAULT_REGION"), metavar="REGION", help="AWS region")
    logs_cmd.add_argument("--follow", action="store_true", help="Keep tailing (Ctrl+C to stop)")
    logs_cmd.add_argument("--since", type=int, default=10, metavar="MINUTES", help="How many minutes back to start (default: 10)")
    logs_cmd.set_defaults(func=_logs)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
