import hashlib
import json
import os
import tempfile
import time
import tomllib
import zipfile

_EXCLUDE_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    ".git",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".tox",
}
_EXCLUDE_FILES = {".env", "cordless.toml", ".DS_Store"}
_EXCLUDE_SUFFIXES = (".pyc", ".pyo")


def _exclude_dir(d):
    return d in _EXCLUDE_DIRS or d.endswith(".egg-info")


_LAMBDA_TRUST_POLICY = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
)
_LAMBDA_BASIC_EXECUTION_POLICY = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"


_KNOWN_DEPLOY_KEYS = {
    "bot",
    "setup",
    "env",
    "function",
    "runtime",
    "defer_worker",
    "role_name",
    "handler",
    "layer_name",
    "region",
    "timeout",
    "memory",
    "bundle_cordless",
    "packages",
    "defer_handler",
    "defer_timeout",
    "defer_memory",
    "policies",
    "architecture",
}


def load_config(source_dir):
    path = os.path.join(source_dir, "cordless.toml")
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        cfg = tomllib.load(f).get("deploy", {})
    unknown = set(cfg) - _KNOWN_DEPLOY_KEYS
    for key in sorted(unknown):
        print(f"cordless: unknown [deploy] key {key!r} in cordless.toml (ignored)")
    return cfg


def build_function_zip(source_dir, bundle_cordless=False, packages=None, python_version="3.12", architecture="x86_64"):
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if not _exclude_dir(d)]
            for fname in files:
                if fname in _EXCLUDE_FILES or fname.endswith(_EXCLUDE_SUFFIXES):
                    continue
                abs_path = os.path.join(root, fname)
                zf.write(abs_path, os.path.relpath(abs_path, source_dir))

        if bundle_cordless:
            from .upload import _cordless_package_dir

            pkg_dir = _cordless_package_dir()
            pkg_parent = os.path.dirname(pkg_dir)
            for root, dirs, files in os.walk(pkg_dir):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for fname in files:
                    if fname.endswith(".pyc"):
                        continue
                    abs_path = os.path.join(root, fname)
                    zf.write(abs_path, os.path.relpath(abs_path, pkg_parent))
            # include dist-info/egg-info so importlib.metadata works inside Lambda
            import glob

            for pattern in ("cordless-*.dist-info", "cordless.egg-info"):
                for dist_info in glob.glob(os.path.join(pkg_parent, pattern)):
                    for root, dirs, files in os.walk(dist_info):
                        for fname in files:
                            abs_path = os.path.join(root, fname)
                            zf.write(abs_path, os.path.relpath(abs_path, pkg_parent))
        if packages:
            pkg_dir = _ensure_packages(packages, python_version, architecture)
            for root, dirs, files in os.walk(pkg_dir):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for fname in files:
                    if fname.endswith(".pyc"):
                        continue
                    abs_path = os.path.join(root, fname)
                    zf.write(abs_path, os.path.relpath(abs_path, pkg_dir))

    return tmp.name


def _packages_cache_dir(packages, python_version, architecture="x86_64"):
    key = hashlib.sha256(json.dumps([sorted(packages), python_version, architecture]).encode()).hexdigest()[:16]
    return os.path.join(os.path.expanduser("~"), ".cache", "cordless", "packages", key)


def _ensure_packages(packages, python_version, architecture="x86_64"):
    """uv-install Lambda-compatible wheels, cached across deploys.

    The cache key is the exact packages list + python version, so unpinned
    specs (e.g. "pillow") stay at whatever version was first installed until
    the list changes or ~/.cache/cordless is cleared.
    """
    cache_dir = _packages_cache_dir(packages, python_version, architecture)
    if os.path.isdir(cache_dir) and os.listdir(cache_dir):
        return cache_dir

    import shutil
    import subprocess
    import sys

    # prefer the uv installed alongside this interpreter (e.g. via cordless[deploy])
    # before falling back to PATH (e.g. brew, the astral install script)
    venv_uv = os.path.join(os.path.dirname(sys.executable), "uv")
    uv = venv_uv if os.path.isfile(venv_uv) else shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv not found — install it: https://docs.astral.sh/uv/getting-started/installation/")

    os.makedirs(os.path.dirname(cache_dir), exist_ok=True)
    staging = tempfile.mkdtemp(dir=os.path.dirname(cache_dir))
    try:
        platform = "aarch64-manylinux2014" if architecture == "arm64" else "x86_64-manylinux2014"
        result = subprocess.run(
            [
                uv,
                "pip",
                "install",
                "--target",
                staging,
                "--python-platform",
                platform,
                "--python-version",
                python_version,
                "--only-binary",
                ":all:",
                *packages,
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip() if result.stderr else ""
            raise RuntimeError(f"uv pip install failed for {packages} (exit {result.returncode}): {stderr}")
        try:
            os.rename(staging, cache_dir)
        except OSError:
            shutil.rmtree(staging, ignore_errors=True)  # concurrent deploy won the race
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return cache_dir


def ensure_iam_role(iam, role_name, extra_policies=None):
    existing = True
    try:
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        existing = False

    if not existing:
        role_arn = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=_LAMBDA_TRUST_POLICY,
        )["Role"]["Arn"]
        iam.attach_role_policy(RoleName=role_name, PolicyArn=_LAMBDA_BASIC_EXECUTION_POLICY)

    for arn in extra_policies or []:
        iam.attach_role_policy(RoleName=role_name, PolicyArn=arn)

    return role_arn


def _cordless_version():
    from importlib.metadata import version

    return version("cordless")


def _publish_cordless_layer(lam, layer_name, python_version=None, architecture="x86_64"):
    from .upload import build_layer_zip

    current_version = _cordless_version()
    # pynacl's cffi dependency is compiled per python version, so layers are
    # runtime-specific. the description keys the reuse check on both
    description = (
        f"cordless_{architecture} {current_version} (python{python_version})"
        if python_version
        else f"cordless_{architecture} {current_version}"
    )

    try:
        for v in _list_all_layer_versions(lam, layer_name):
            if v.get("Description") == description:
                return v["LayerVersionArn"]
    except lam.exceptions.ResourceNotFoundException:
        pass

    from .upload import _LAMBDA_RUNTIMES

    runtimes = [f"python{python_version}"] if python_version else _LAMBDA_RUNTIMES

    zip_path = build_layer_zip(python_version, architecture)
    try:
        with open(zip_path, "rb") as f:
            resp = lam.publish_layer_version(
                LayerName=layer_name,
                Description=description,
                Content={"ZipFile": f.read()},
                CompatibleRuntimes=runtimes,
            )
        return resp["LayerVersionArn"]
    finally:
        os.unlink(zip_path)


def _list_all_apis(apigw):
    return apigw.get_paginator("get_apis").paginate().build_full_result()["Items"]


def _list_all_layer_versions(lam, layer_name):
    paginator = lam.get_paginator("list_layer_versions")
    return paginator.paginate(LayerName=layer_name).build_full_result()["LayerVersions"]


def _list_all_rules(events, prefix):
    return events.get_paginator("list_rules").paginate(NamePrefix=prefix).build_full_result()["Rules"]


def _function_exists(lam, function_name):
    try:
        config = lam.get_function_configuration(FunctionName=function_name)
        return True, config["FunctionArn"]
    except lam.exceptions.ResourceNotFoundException:
        return False, None


def _env_vars(env):
    return {"Variables": env or {}}


def _create_function(
    lam,
    function_name,
    zip_path,
    role_arn,
    handler,
    runtime,
    layer_arn,
    env,
    timeout=10,
    memory_size=256,
    architecture="x86_64",
):
    with open(zip_path, "rb") as f:
        zip_bytes = f.read()

    # IAM is eventually consistent and a brand-new role gets rejected for ~5-10s,
    # so retry instead of sleeping a fixed worst-case delay up front
    for attempt in range(15):
        try:
            resp = lam.create_function(
                FunctionName=function_name,
                Runtime=runtime,
                Role=role_arn,
                Handler=handler,
                Code={"ZipFile": zip_bytes},
                Layers=[layer_arn] if layer_arn else [],
                Environment=_env_vars(env),
                Timeout=timeout,
                MemorySize=memory_size,
                Architectures=[architecture],
            )
            break
        except lam.exceptions.InvalidParameterValueException as exc:
            if "role" not in str(exc).lower() or attempt == 14:
                raise
            time.sleep(2)
    lam.get_waiter("function_active").wait(FunctionName=function_name)
    return resp["FunctionArn"]


def _update_function(
    lam, function_name, zip_path, handler, runtime, layer_arn, env, timeout=10, memory_size=256, architecture="x86_64"
):
    with open(zip_path, "rb") as f:
        lam.update_function_code(FunctionName=function_name, ZipFile=f.read(), Architectures=[architecture])
    lam.get_waiter("function_updated").wait(FunctionName=function_name)

    lam.update_function_configuration(
        FunctionName=function_name,
        Handler=handler,
        Runtime=runtime,
        Layers=[layer_arn] if layer_arn else [],
        Environment=_env_vars(env),
        Timeout=timeout,
        MemorySize=memory_size,
    )
    lam.get_waiter("function_updated").wait(FunctionName=function_name)


def _ensure_api_gateway(apigw, lam, function_name, function_arn, region, account_id):
    api_name = f"{function_name}-api"

    # Reuse existing API if one with this name exists
    apis = _list_all_apis(apigw)
    existing = next((a for a in apis if a["Name"] == api_name), None)

    if existing:
        api_id = existing["ApiId"]
        endpoint = existing["ApiEndpoint"]
    else:
        api = apigw.create_api(Name=api_name, ProtocolType="HTTP")
        api_id = api["ApiId"]
        endpoint = api["ApiEndpoint"]

        integration = apigw.create_integration(
            ApiId=api_id,
            IntegrationType="AWS_PROXY",
            IntegrationUri=function_arn,
            PayloadFormatVersion="2.0",
        )

        apigw.create_route(
            ApiId=api_id,
            RouteKey="POST /",
            Target=f"integrations/{integration['IntegrationId']}",
        )

        apigw.create_stage(ApiId=api_id, StageName="$default", AutoDeploy=True)

    # Always refresh the Lambda invoke permission for this API
    source_arn = f"arn:aws:execute-api:{region}:{account_id}:{api_id}/*/*"
    try:
        lam.remove_permission(FunctionName=function_name, StatementId="APIGatewayInvoke")
    except lam.exceptions.ResourceNotFoundException:
        pass

    lam.add_permission(
        FunctionName=function_name,
        StatementId="APIGatewayInvoke",
        Action="lambda:InvokeFunction",
        Principal="apigateway.amazonaws.com",
        SourceArn=source_arn,
    )

    return endpoint


def _allow_worker_invoke(iam, role_name, worker_arn):
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="cordless-worker-invoke",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "lambda:InvokeFunction",
                        "Resource": worker_arn,
                    }
                ],
            }
        ),
    )


def deploy(
    function_name,
    role_name,
    handler,
    source_dir,
    runtime,
    layer_name,
    env,
    region,
    timeout=10,
    memory=256,
    bundle_cordless=False,
    packages=None,
    python_version="3.12",
    defer_worker=None,
    defer_handler="lambda_function.worker_handler",
    defer_timeout=30,
    defer_memory=256,
    policies=None,
    crons=None,
    architecture="x86_64",
):
    if not function_name:
        raise SystemExit("Function name is required: pass --function or set [deploy] function in cordless.toml")

    from ._aws import get_session
    from ._progress import Spinner, success

    session = get_session(region)
    region = region or session.region_name
    iam = session.client("iam")
    lam = session.client("lambda")
    apigw = session.client("apigatewayv2")
    account_id = session.client("sts").get_caller_identity()["Account"]

    print()

    with Spinner("IAM role"):
        role_arn = ensure_iam_role(iam, role_name, extra_policies=policies)

    if bundle_cordless:
        with Spinner(f"cordless  {_cordless_version()} (local)"):
            layer_arn = None
    else:
        with Spinner(f"cordless layer  {_cordless_version()}"):
            layer_arn = _publish_cordless_layer(lam, layer_name, python_version, architecture)

    with Spinner("packaging"):
        zip_path = build_function_zip(
            source_dir,
            bundle_cordless=bundle_cordless,
            packages=packages,
            python_version=python_version,
            architecture=architecture,
        )

    try:
        exists, function_arn = _function_exists(lam, function_name)
        verb = "updating" if exists else "creating"
        with Spinner(f"{verb}  {function_name}"):
            if exists:
                _update_function(
                    lam,
                    function_name,
                    zip_path,
                    handler,
                    runtime,
                    layer_arn or "",
                    env,
                    timeout=timeout,
                    memory_size=memory,
                    architecture=architecture,
                )
            else:
                function_arn = _create_function(
                    lam,
                    function_name,
                    zip_path,
                    role_arn,
                    handler,
                    runtime,
                    layer_arn or "",
                    env,
                    timeout=timeout,
                    memory_size=memory,
                    architecture=architecture,
                )

        with Spinner("API Gateway"):
            url = _ensure_api_gateway(apigw, lam, function_name, function_arn, region, account_id)

        if defer_worker:
            w_exists, worker_arn = _function_exists(lam, defer_worker)
            w_verb = "updating" if w_exists else "creating"
            with Spinner(f"{w_verb}  {defer_worker}"):
                if w_exists:
                    _update_function(
                        lam,
                        defer_worker,
                        zip_path,
                        defer_handler,
                        runtime,
                        layer_arn,
                        env,
                        timeout=defer_timeout,
                        memory_size=defer_memory,
                        architecture=architecture,
                    )
                else:
                    worker_arn = _create_function(
                        lam,
                        defer_worker,
                        zip_path,
                        role_arn,
                        defer_handler,
                        runtime,
                        layer_arn,
                        env,
                        timeout=defer_timeout,
                        memory_size=defer_memory,
                        architecture=architecture,
                    )
                # deferred handlers aren't idempotent, never let Lambda re-run them on error
                lam.put_function_event_invoke_config(FunctionName=defer_worker, MaximumRetryAttempts=0)
    finally:
        os.unlink(zip_path)

    if defer_worker:
        with Spinner("wiring worker"):
            _allow_worker_invoke(iam, role_name, worker_arn)
            lam.update_function_configuration(
                FunctionName=function_name,
                Environment=_env_vars({**env, "CORDLESS_WORKER_FUNCTION": defer_worker}),
            )
            lam.get_waiter("function_updated").wait(FunctionName=function_name)

    # run even when crons is empty so rules for deleted crons get cleaned up
    if crons is not None:
        cron_target = defer_worker or function_name
        _, cron_arn = _function_exists(lam, cron_target)
        events = session.client("events")
        with Spinner(f"cron schedules ({len(crons)})"):
            _wire_crons(events, lam, function_name, cron_target, cron_arn, crons)

    success(url)
    return url


def _wire_crons(events, lam, function_name, target_fn, target_arn, crons):
    if crons:
        # crons are fire-and-forget; retries would double/triple-send messages
        lam.put_function_event_invoke_config(FunctionName=target_fn, MaximumRetryAttempts=0)

    prefix = f"{function_name}-cron-"
    wanted = {f"{prefix}{name}" for name in crons}
    for rule in _list_all_rules(events, prefix):
        if rule["Name"] in wanted:
            continue
        targets = events.list_targets_by_rule(Rule=rule["Name"]).get("Targets", [])
        target_ids = [t["Id"] for t in targets]
        if target_ids:
            events.remove_targets(Rule=rule["Name"], Ids=target_ids)
        events.delete_rule(Name=rule["Name"])
        # remove the invoke permission from whichever function was actually targeted,
        # which may differ from the current target_fn if defer_worker changed
        cron_name = rule["Name"][len(prefix) :]
        for target in targets:
            fn_name = target["Arn"].split(":")[-1]
            try:
                lam.remove_permission(FunctionName=fn_name, StatementId=f"cordless-cron-{cron_name}")
            except lam.exceptions.ResourceNotFoundException:
                pass

    for name, schedule in crons.items():
        rule_name = f"{function_name}-cron-{name}"
        rule_arn = events.put_rule(Name=rule_name, ScheduleExpression=schedule)["RuleArn"]
        events.put_targets(
            Rule=rule_name,
            Targets=[
                {
                    "Id": "cordless",
                    "Arn": target_arn,
                    "Input": json.dumps({"_cordless_cron": name}),
                }
            ],
        )
        statement_id = f"cordless-cron-{name}"
        try:
            lam.remove_permission(FunctionName=target_fn, StatementId=statement_id)
        except lam.exceptions.ResourceNotFoundException:
            pass
        lam.add_permission(
            FunctionName=target_fn,
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=rule_arn,
        )


def destroy(function_name, role_name, region, defer_worker=None, layer_name=None):
    if not function_name:
        raise SystemExit("Function name is required: pass --function or set [deploy] function in cordless.toml")

    from ._aws import get_session
    from ._progress import Spinner

    session = get_session(region)
    iam = session.client("iam")
    lam = session.client("lambda")
    apigw = session.client("apigatewayv2")
    events = session.client("events")
    logs = session.client("logs")

    print()

    api_name = f"{function_name}-api"
    with Spinner(f"API Gateway  {api_name}"):
        apis = _list_all_apis(apigw)
        existing = next((a for a in apis if a["Name"] == api_name), None)
        if existing:
            apigw.delete_api(ApiId=existing["ApiId"])

    with Spinner("cron schedules"):
        rules = _list_all_rules(events, f"{function_name}-cron-")
        for rule in rules:
            target_ids = [t["Id"] for t in events.list_targets_by_rule(Rule=rule["Name"]).get("Targets", [])]
            if target_ids:
                events.remove_targets(Rule=rule["Name"], Ids=target_ids)
            events.delete_rule(Name=rule["Name"])

    for fn in [function_name] + ([defer_worker] if defer_worker else []):
        with Spinner(f"Lambda  {fn}"):
            try:
                lam.delete_function(FunctionName=fn)
            except lam.exceptions.ResourceNotFoundException:
                pass
            try:
                logs.delete_log_group(logGroupName=f"/aws/lambda/{fn}")
            except logs.exceptions.ResourceNotFoundException:
                pass

    with Spinner(f"IAM role  {role_name}"):
        try:
            for policy in iam.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", []):
                iam.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
            for policy in iam.list_role_policies(RoleName=role_name).get("PolicyNames", []):
                iam.delete_role_policy(RoleName=role_name, PolicyName=policy)
            iam.delete_role(RoleName=role_name)
        except iam.exceptions.NoSuchEntityException:
            pass

    if layer_name:
        with Spinner(f"Lambda layer  {layer_name}"):
            for v in _list_all_layer_versions(lam, layer_name):
                lam.delete_layer_version(LayerName=layer_name, VersionNumber=v["Version"])

    print(f"  ✓ destroyed {function_name}")
