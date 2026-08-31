"""Read-only diagnostics: AWS credentials, IAM role, Discord app config, and
deployed Lambda function state. Nothing here creates or modifies anything -
`cordless deploy` is still what fixes what this finds."""

import re

from ._progress import _BOLD, _DIM, _GREEN, _RED, _RESET, _YELLOW, wait

_PUBLIC_KEY_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# Never printed raw in a drift/mismatch report - only presence and match/mismatch.
_SECRET_ENV_KEYS = {"DISCORD_PUBLIC_KEY", "DISCORD_BOT_TOKEN", "DISCORD_CLIENT_SECRET"}
_DRIFT_CHECK_KEYS = (
    "DISCORD_PUBLIC_KEY",
    "DISCORD_BOT_TOKEN",
    "DISCORD_CLIENT_ID",
    "DISCORD_CLIENT_SECRET",
    "DISCORD_GUILD_ID",
)


def check_aws_credentials(region=None):
    """Returns (ok, session_or_none, detail)."""
    from ._aws import get_session

    try:
        session = get_session(region, validate=True)
    except SystemExit as exc:
        return False, None, str(exc).strip()
    identity = session.client("sts").get_caller_identity()
    return True, session, f"account {identity['Account']}"


def check_iam_role(iam, role_name, defer_worker=None, ratelimit=False):
    """Read-only checks against an existing role - never creates one.
    Returns a list of (severity, label, detail)."""
    checks = []
    try:
        iam.get_role(RoleName=role_name)
    except iam.exceptions.NoSuchEntityException:
        return [("fail", "IAM role", f"{role_name!r} not found")]
    except Exception as exc:
        return [("fail", "IAM role", f"could not verify ({exc})")]

    checks.append(("ok", "IAM role", f"{role_name!r} exists"))

    attached = iam.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", [])
    has_basic = any(p["PolicyName"] == "AWSLambdaBasicExecutionRole" for p in attached)
    checks.append(
        ("ok" if has_basic else "fail", "Basic execution policy", "attached" if has_basic else "not attached")
    )

    if defer_worker:
        try:
            iam.get_role_policy(RoleName=role_name, PolicyName="cordless-worker-invoke")
            checks.append(("ok", "Worker invoke policy", "present"))
        except iam.exceptions.NoSuchEntityException:
            checks.append(("fail", "Worker invoke policy", "not found - worker invocations will fail"))

    if ratelimit:
        try:
            iam.get_role_policy(RoleName=role_name, PolicyName="cordless-ratelimit-table")
            checks.append(("ok", "Rate limit table policy", "present"))
        except iam.exceptions.NoSuchEntityException:
            checks.append(("fail", "Rate limit table policy", "not found - rate limiting will fail"))

    return checks


def check_discord_config(env):
    """`env` is the resolved DISCORD_* dict (same layering `cordless deploy`
    uses: .env + .env.<environment> + cordless.toml + process env). Returns
    a list of (severity, label, detail)."""
    checks = []

    public_key = env.get("DISCORD_PUBLIC_KEY")
    if not public_key:
        checks.append(("fail", "DISCORD_PUBLIC_KEY", "missing"))
    elif not _PUBLIC_KEY_RE.match(public_key):
        checks.append(("fail", "DISCORD_PUBLIC_KEY", "set, but doesn't look like a 64-char hex Ed25519 key"))
    else:
        checks.append(("ok", "DISCORD_PUBLIC_KEY", "present, well-formed"))

    token = env.get("DISCORD_BOT_TOKEN")
    client_id = env.get("DISCORD_CLIENT_ID")
    client_secret = env.get("DISCORD_CLIENT_SECRET")

    if token:
        from .register import _get_application_id

        try:
            app_id = _get_application_id(token)
            checks.append(("ok", "Bot token", f"valid (application id {app_id})"))
        except RuntimeError as exc:
            checks.append(("fail", "Bot token", str(exc)))
    elif client_id and client_secret:
        from .register import _get_client_credentials_token

        try:
            _get_client_credentials_token(client_id, client_secret)
            checks.append(("ok", "Client credentials", "valid"))
        except RuntimeError as exc:
            checks.append(("fail", "Client credentials", str(exc)))
    else:
        checks.append(
            ("fail", "Discord credentials", "no DISCORD_BOT_TOKEN or DISCORD_CLIENT_ID/DISCORD_CLIENT_SECRET set")
        )

    return checks


def check_env_drift(lam, function_name, local_env):
    """Compare the deployed function's env vars against the locally resolved
    ones for the handful of Discord credential keys. Reports only presence
    and match/mismatch for secret-shaped keys - never the actual value."""
    checks = []
    try:
        deployed_env = (
            lam.get_function_configuration(FunctionName=function_name).get("Environment", {}).get("Variables", {})
        )
    except Exception as exc:
        return [("fail", "Env var drift", f"could not verify ({exc})")]

    for key in _DRIFT_CHECK_KEYS:
        local_value = local_env.get(key)
        deployed_value = deployed_env.get(key)
        if not local_value and not deployed_value:
            continue
        label = f"{key} (deployed)"
        if local_value and deployed_value:
            matches = local_value == deployed_value
            if matches:
                checks.append(("ok", label, "matches local"))
            elif key in _SECRET_ENV_KEYS:
                checks.append(("fail", label, "differs from local"))
            else:
                checks.append(("fail", label, f"deployed={deployed_value!r}, local={local_value!r}"))
        elif local_value and not deployed_value:
            checks.append(("fail", label, "set locally but missing on the deployed function"))
        else:
            checks.append(("fail", label, "set on the deployed function but missing locally"))

    return checks


def check_deployed_function(
    lam,
    apigw,
    events,
    dynamodb,
    function_name,
    defer_worker,
    crons,
    keep_warm,
    ratelimit,
    table_name,
    local_env,
    routes=None,
):
    from .deploy import _function_exists, _has_api_gateway, _has_function_url, _health_check

    exists, _ = _function_exists(lam, function_name)
    if not exists:
        return [("warn", "Deployed function", f"{function_name!r} not deployed yet - run `cordless deploy`")]

    if _has_function_url(lam, function_name):
        endpoint = "function_url"
    elif _has_api_gateway(apigw, function_name):
        endpoint = "api_gateway"
    else:
        endpoint = "function_url"

    health = _health_check(
        lam,
        apigw,
        events,
        dynamodb,
        function_name,
        defer_worker,
        endpoint,
        crons,
        keep_warm,
        ratelimit,
        table_name,
        routes,
    )
    checks = [("ok" if ok else "fail", label, detail) for ok, label, detail in health]
    checks.extend(check_env_drift(lam, function_name, local_env))
    return checks


def run(
    function_name,
    role_name,
    region,
    defer_worker=None,
    crons=None,
    keep_warm=None,
    ratelimit=False,
    local_env=None,
    routes=None,
    on_section=None,
):
    """Run every diagnostic check, one section at a time. Returns (sections, ok):
    `sections` is [(title, [(severity, label, detail), ...]), ...] for
    printing; `ok` is False if any check came back "fail" (warnings alone
    don't fail it).

    Pass `on_section(title, checks)` to be called as soon as each section
    finishes, so a caller can print progressively instead of waiting for
    every section (AWS, Discord, IAM, Lambda each make several blocking
    network calls) to complete before anything shows up."""
    local_env = local_env or {}
    sections = []

    def _emit(title, checks):
        sections.append((title, checks))
        if on_section is not None:
            on_section(title, checks)

    aws_ok, session, aws_detail = wait("AWS", lambda: check_aws_credentials(region))
    _emit("AWS", [("ok" if aws_ok else "fail", "Credentials", aws_detail)])

    _emit("Discord", wait("Discord", lambda: check_discord_config(local_env)))

    if not role_name:
        iam_checks = [("warn", "IAM role", "no function configured - nothing to check")]
    elif not aws_ok:
        iam_checks = [("warn", "IAM role", "skipped - AWS credentials not available")]
    else:
        assert session is not None
        iam_checks = wait(
            "IAM",
            lambda: check_iam_role(session.client("iam"), role_name, defer_worker=defer_worker, ratelimit=ratelimit),
        )
    _emit("IAM", iam_checks)

    if not function_name:
        lambda_checks = [("warn", "Deployed function", "no function configured - nothing to check")]
    elif not aws_ok:
        lambda_checks = [("warn", "Deployed function", "skipped - AWS credentials not available")]
    else:
        assert session is not None
        from .deploy import ratelimit_table_name

        table_name = ratelimit_table_name(function_name) if ratelimit else None
        lambda_checks = wait(
            "Lambda",
            lambda: check_deployed_function(
                session.client("lambda"),
                session.client("apigatewayv2"),
                session.client("events"),
                session.client("dynamodb"),
                function_name,
                defer_worker,
                crons or {},
                keep_warm,
                ratelimit,
                table_name,
                local_env,
                routes,
            ),
        )
    _emit("Lambda", lambda_checks)

    ok = not any(severity == "fail" for _, checks in sections for severity, _, _ in checks)
    return sections, ok


def _mark(severity):
    if severity == "ok":
        return f"{_GREEN}✓{_RESET}"
    if severity == "warn":
        return f"{_YELLOW}⚠{_RESET}"
    return f"{_RED}✗{_RESET}"


def print_section(title, checks):
    print(f"\n  {_BOLD}{title}{_RESET}")
    for severity, label, detail in checks:
        print(f"    {_mark(severity)} {label}: {detail}")


def print_report(sections):
    for title, checks in sections:
        print_section(title, checks)
    print(f"\n  {_DIM}── done ──{_RESET}\n")
