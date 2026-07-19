import ast
import hashlib
import json
import os
import re
import sys
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


def _exclude_file(f):
    return f in _EXCLUDE_FILES or f.endswith(_EXCLUDE_SUFFIXES) or f.startswith(".env.")


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
    "ratelimit",
    "endpoint",
    "keep-warm",
}

_DEFAULT_KEEPWARM_SCHEDULE = "rate(5 minutes)"


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


# always available on a deployed function regardless of `packages`: boto3/botocore
# ship with every Lambda Python runtime, nacl comes from cordless's own layer, and
# "cordless" is this project itself
_ALWAYS_AVAILABLE_IMPORTS = {"boto3", "botocore", "nacl", "cordless"}

# distribution name -> import name, for the common cases where they differ, so a
# correctly-declared package doesn't get flagged as an unresolved import. Not
# exhaustive - just the ones people actually hit.
_DIST_TO_IMPORT_NAME = {
    "pillow": "pil",
    "pyyaml": "yaml",
    "beautifulsoup4": "bs4",
    "python-dotenv": "dotenv",
    "opencv-python": "cv2",
    "opencv-python-headless": "cv2",
    "scikit-learn": "sklearn",
    "python-dateutil": "dateutil",
    "protobuf": "google",
    "pyjwt": "jwt",
    "pynacl": "nacl",
}

# directories that are real project files (so still zipped) but never run on
# Lambda, so their imports (test frameworks etc.) shouldn't count against packages
_SCAN_EXCLUDE_DIRS = {"tests", "test"}


def _declared_package_names(packages):
    """Bare, lowercase distribution names from `packages`, stripped of version
    specifiers/extras/markers, e.g. "pillow==11.2.0" -> "pillow"."""
    names = set()
    for spec in packages or ():
        name = re.split(r"[<>=!~\[; ]", spec, maxsplit=1)[0].strip().lower()
        if name:
            names.add(name)
    return names


def _local_module_names(source_dir):
    """Top-level modules/packages that are this project's own code, not a pip
    dependency - anything sitting directly in source_dir."""
    names = set()
    try:
        entries = os.listdir(source_dir)
    except OSError:
        return names
    for entry in entries:
        if entry.endswith(".py"):
            names.add(entry[:-3])
        elif os.path.isdir(os.path.join(source_dir, entry)) and not _exclude_dir(entry):
            names.add(entry)
    return names


def _imported_top_level_names(source_dir):
    """Every top-level module name imported anywhere in the files that get
    bundled into the zip. Static (ast-based), so it can't see imports gated
    behind a runtime condition (try/except ImportError, sys.version checks)."""
    names = set()
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if not _exclude_dir(d) and d not in _SCAN_EXCLUDE_DIRS]
        for fname in files:
            if not fname.endswith(".py") or _exclude_file(fname):
                continue
            path = os.path.join(root, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=path)
            except (SyntaxError, OSError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        names.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0 and node.module:
                        names.add(node.module.split(".")[0])
    return names


def scan_missing_packages(source_dir, packages=None):
    """Best-effort: top-level imports in the bundled source that resolve to
    neither the standard library, this project's own local code, nor a
    declared `packages` entry - almost always a forgotten `packages` line
    for something that works fine locally (already installed) but doesn't
    exist on Lambda. Static analysis, so callers must only ever warn on this
    (see the `packages` list itself for why this can't be a hard failure)."""
    declared = _declared_package_names(packages)
    resolved = set(declared) | _ALWAYS_AVAILABLE_IMPORTS
    for dist, import_name in _DIST_TO_IMPORT_NAME.items():
        if dist in declared:
            resolved.add(import_name)

    local = _local_module_names(source_dir)
    stdlib = set(sys.stdlib_module_names)

    missing = set()
    for name in _imported_top_level_names(source_dir):
        if name in local or name.lower() in stdlib or name.lower() in resolved:
            continue
        missing.add(name)
    return sorted(missing)


def build_function_zip(source_dir, bundle_cordless=False, packages=None, python_version="3.12", architecture="x86_64"):
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    # pynacl (bundle_cordless extras) and a user's own `packages = ["pynacl"]`
    # can resolve to the same cache dir, so this dedupes to avoid writing the
    # same file into the zip twice
    written = set()

    def _write(zf, abs_path, arcname):
        if arcname in written:
            return
        written.add(arcname)
        zf.write(abs_path, arcname)

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if not _exclude_dir(d)]
            for fname in files:
                if _exclude_file(fname):
                    continue
                abs_path = os.path.join(root, fname)
                _write(zf, abs_path, os.path.relpath(abs_path, source_dir))

        if bundle_cordless:
            from .upload import _cordless_package_dir, _is_runtime_file, _layer_extras_dir

            pkg_dir = _cordless_package_dir()
            pkg_parent = os.path.dirname(pkg_dir)
            for root, dirs, files in os.walk(pkg_dir):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for fname in files:
                    if not _is_runtime_file(fname):
                        continue
                    abs_path = os.path.join(root, fname)
                    _write(zf, abs_path, os.path.relpath(abs_path, pkg_parent))
            # include dist-info/egg-info so importlib.metadata works inside Lambda
            import glob

            for pattern in ("cordless-*.dist-info", "cordless.egg-info"):
                for dist_info in glob.glob(os.path.join(pkg_parent, pattern)):
                    for root, dirs, files in os.walk(dist_info):
                        for fname in files:
                            abs_path = os.path.join(root, fname)
                            _write(zf, abs_path, os.path.relpath(abs_path, pkg_parent))

            # same pynacl bundling the layer path gets, so bundle_cordless doesn't
            # silently fall back to slow signature verification
            extras_dir = _layer_extras_dir(python_version, architecture)
            if extras_dir:
                for root, dirs, files in os.walk(extras_dir):
                    dirs[:] = [d for d in dirs if d != "__pycache__"]
                    for fname in files:
                        if fname.endswith(".pyc"):
                            continue
                        abs_path = os.path.join(root, fname)
                        _write(zf, abs_path, os.path.relpath(abs_path, extras_dir))
        if packages:
            pkg_dir = _ensure_packages(packages, python_version, architecture)
            for root, dirs, files in os.walk(pkg_dir):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for fname in files:
                    if fname.endswith(".pyc"):
                        continue
                    abs_path = os.path.join(root, fname)
                    _write(zf, abs_path, os.path.relpath(abs_path, pkg_dir))

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
                CompatibleArchitectures=[architecture],
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


def _has_api_gateway(apigw, function_name):
    api_name = f"{function_name}-api"
    return any(a["Name"] == api_name for a in _list_all_apis(apigw))


def _has_function_url(lam, function_name):
    try:
        lam.get_function_url_config(FunctionName=function_name)
        return True
    except lam.exceptions.ResourceNotFoundException:
        return False


def _ensure_function_url(lam, function_name):
    """Like _ensure_api_gateway, but a direct Lambda Function URL - no API
    Gateway hop, no separate service to provision or tear down (deleting the
    function removes its Function URL along with it).

    A public (AuthType=NONE) function URL needs two resource-policy
    statements, not one: lambda:InvokeFunctionUrl, and - required by AWS
    since October 2025 - a second lambda:InvokeFunction statement gated on
    InvokedViaFunctionUrl. Without the second one every request 403s before
    it ever reaches the handler, which is exactly what silently breaks
    Discord's endpoint verification (it never gets any response to sign
    against, just a flat rejection).

    Both add_permission calls run every time, even when the URL config
    already exists - not just on first creation. A function whose URL was
    created by an older cordless version (or a partially failed earlier
    attempt) may already have the config but be missing one or both
    permission statements; returning early here would leave it stuck
    broken instead of healing it on the next deploy.
    """
    try:
        config = lam.get_function_url_config(FunctionName=function_name)
    except lam.exceptions.ResourceNotFoundException:
        config = lam.create_function_url_config(FunctionName=function_name, AuthType="NONE")

    try:
        lam.add_permission(
            FunctionName=function_name,
            StatementId="FunctionURLAllowPublicAccess",
            Action="lambda:InvokeFunctionUrl",
            Principal="*",
            FunctionUrlAuthType="NONE",
        )
    except lam.exceptions.ResourceConflictException:
        pass

    try:
        lam.add_permission(
            FunctionName=function_name,
            StatementId="FunctionURLInvokeAllowPublicAccess",
            Action="lambda:InvokeFunction",
            Principal="*",
            InvokedViaFunctionUrl=True,
        )
    except lam.exceptions.ResourceConflictException:
        pass

    return config["FunctionUrl"]


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


def ratelimit_table_name(function_name):
    return f"{function_name}-ratelimit"


def ensure_ratelimit_table(dynamodb, table_name):
    try:
        dynamodb.describe_table(TableName=table_name)
        return
    except dynamodb.exceptions.ResourceNotFoundException:
        pass

    dynamodb.create_table(
        TableName=table_name,
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
        BillingMode="PAY_PER_REQUEST",
    )
    dynamodb.get_waiter("table_exists").wait(TableName=table_name)
    dynamodb.update_time_to_live(
        TableName=table_name,
        TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
    )


def _allow_ratelimit_table(iam, role_name, table_arn):
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="cordless-ratelimit-table",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["dynamodb:GetItem", "dynamodb:PutItem"],
                        "Resource": table_arn,
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
    architecture=None,
    ratelimit=False,
    endpoint=None,
    keep_warm=None,
):
    if not function_name:
        raise SystemExit("Function name is required: pass --function or set [deploy] function in cordless.toml")

    from ._aws import get_session
    from ._progress import Spinner, success, summary

    session = get_session(region)
    region = region or session.region_name
    iam = session.client("iam")
    lam = session.client("lambda")
    apigw = session.client("apigatewayv2")
    account_id = session.client("sts").get_caller_identity()["Account"]

    if architecture is None:
        # AWS won't let an existing function's architecture change in place, so
        # an unset architecture keeps whatever's already deployed. arm64 is only
        # the default for a function that doesn't exist yet.
        try:
            existing_config = lam.get_function_configuration(FunctionName=function_name)
            architecture = existing_config.get("Architectures", ["x86_64"])[0]
        except lam.exceptions.ResourceNotFoundException:
            architecture = "arm64"

    if endpoint is None:
        # keep whichever endpoint an existing function already has; only a
        # brand new function gets the simpler, lower-latency default
        if _has_function_url(lam, function_name):
            endpoint = "function_url"
        elif _has_api_gateway(apigw, function_name):
            endpoint = "api_gateway"
        else:
            endpoint = "function_url"

    print()

    with Spinner("IAM role"):
        role_arn = ensure_iam_role(iam, role_name, extra_policies=policies)

    table_name = None
    if ratelimit:
        table_name = ratelimit_table_name(function_name)
        with Spinner("rate limit table"):
            ensure_ratelimit_table(session.client("dynamodb"), table_name)
            table_arn = f"arn:aws:dynamodb:{region}:{account_id}:table/{table_name}"
            _allow_ratelimit_table(iam, role_name, table_arn)
        env = {**env, "CORDLESS_RATELIMIT_TABLE": table_name}

    from . import upload as _upload

    _upload.pynacl_bundle_failed = False

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

        if endpoint == "function_url":
            with Spinner("function URL"):
                url = _ensure_function_url(lam, function_name)
        else:
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

    with Spinner("keep-warm" if keep_warm else "keep-warm (off)"):
        _wire_keepwarm(session.client("events"), lam, function_name, function_arn, keep_warm)

    health = _health_check(
        lam,
        apigw,
        session.client("events"),
        session.client("dynamodb"),
        function_name,
        defer_worker,
        endpoint,
        crons,
        keep_warm,
        ratelimit,
        table_name,
    )

    missing_packages = scan_missing_packages(source_dir, packages)
    package_check = (
        [
            (
                False,
                "Package check",
                f"{', '.join(missing_packages)} (see https://cordless.dev/guides/deploying/#extra-packages)",
            )
        ]
        if missing_packages
        else []
    )

    summary(
        [
            (True, "Runtime", runtime),
            (
                not _upload.pynacl_bundle_failed,
                "Signature verification",
                "pynacl" if not _upload.pynacl_bundle_failed else "pure-Python Ed25519 (slower than pynacl)",
            ),
            *package_check,
            *health,
        ]
    )
    success(url)
    return url


def _health_check(
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
):
    """Describe-only post-deploy checks - no invocations, no AWS cost. Confirms
    the pieces deploy() just wired are actually present and in the expected
    shape, not just that the API calls that created them didn't raise.
    Returns a list of (ok, label, detail) tuples for summary()."""
    checks = []

    try:
        config = lam.get_function_configuration(FunctionName=function_name)
        state = config.get("State", "unknown")
        checks.append((state == "Active", "Function", state))
    except Exception as exc:
        checks.append((False, "Function", f"could not verify ({exc})"))

    if defer_worker:
        try:
            config = lam.get_function_configuration(FunctionName=defer_worker)
            state = config.get("State", "unknown")
            checks.append((state == "Active", "Worker function", state))
        except Exception as exc:
            checks.append((False, "Worker function", f"could not verify ({exc})"))

    if endpoint == "function_url":
        try:
            lam.get_function_url_config(FunctionName=function_name)
            policy = json.loads(lam.get_policy(FunctionName=function_name)["Policy"])
            actions = {s["Action"] for s in policy["Statement"]}
            has_both = {"lambda:InvokeFunctionUrl", "lambda:InvokeFunction"}.issubset(actions)
            checks.append(
                (
                    has_both,
                    "Function URL permissions",
                    "both required statements present" if has_both else "missing lambda:InvokeFunction statement",
                )
            )
        except Exception as exc:
            checks.append((False, "Function URL", f"could not verify ({exc})"))
    else:
        try:
            api_name = f"{function_name}-api"
            exists = any(a["Name"] == api_name for a in _list_all_apis(apigw))
            checks.append((exists, "API Gateway", "present" if exists else "not found"))
        except Exception as exc:
            checks.append((False, "API Gateway", f"could not verify ({exc})"))

    if crons:
        target = defer_worker or function_name
        missing = []
        for name in crons:
            rule_name = f"{function_name}-cron-{name}"
            try:
                targets = events.list_targets_by_rule(Rule=rule_name).get("Targets", [])
                if not any(t["Arn"].endswith(f":{target}") for t in targets):
                    missing.append(name)
            except events.exceptions.ResourceNotFoundException:
                missing.append(name)
        detail = "all present" if not missing else f"missing/misdirected: {', '.join(missing)}"
        checks.append((not missing, "Cron rules", detail))

    if keep_warm:
        rule_name = f"{function_name}-keepwarm"
        try:
            targets = events.list_targets_by_rule(Rule=rule_name).get("Targets", [])
            ok = any(t["Arn"].endswith(f":{function_name}") for t in targets)
            checks.append((ok, "Keep-warm rule", "targets main function" if ok else "not targeting main function"))
        except events.exceptions.ResourceNotFoundException:
            checks.append((False, "Keep-warm rule", "not found"))

    if ratelimit:
        try:
            state = dynamodb.describe_table(TableName=table_name)["Table"]["TableStatus"]
            checks.append((state == "ACTIVE", "Rate limit table", state))
        except Exception as exc:
            checks.append((False, "Rate limit table", f"could not verify ({exc})"))

    return checks


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


def _keepwarm_schedule(keep_warm):
    if keep_warm is True:
        return _DEFAULT_KEEPWARM_SCHEDULE
    if isinstance(keep_warm, str):
        return keep_warm
    return None


def _wire_keepwarm(events, lam, function_name, function_arn, keep_warm):
    """Ping the main function directly on a schedule so it doesn't go cold
    between real invocations. Always targets the main function, never the
    worker - regular crons can't do this, since they all share one target
    (defer_worker if it's set, otherwise the main function)."""
    schedule = _keepwarm_schedule(keep_warm)
    if not schedule:
        _remove_keepwarm(events, lam, function_name)
        return

    rule_name = f"{function_name}-keepwarm"
    statement_id = "cordless-keepwarm"
    rule_arn = events.put_rule(Name=rule_name, ScheduleExpression=schedule)["RuleArn"]
    events.put_targets(
        Rule=rule_name,
        Targets=[{"Id": "cordless", "Arn": function_arn, "Input": json.dumps({"_cordless_keepwarm": True})}],
    )
    try:
        lam.remove_permission(FunctionName=function_name, StatementId=statement_id)
    except lam.exceptions.ResourceNotFoundException:
        pass
    lam.add_permission(
        FunctionName=function_name,
        StatementId=statement_id,
        Action="lambda:InvokeFunction",
        Principal="events.amazonaws.com",
        SourceArn=rule_arn,
    )


def _remove_keepwarm(events, lam, function_name):
    rule_name = f"{function_name}-keepwarm"
    try:
        targets = events.list_targets_by_rule(Rule=rule_name).get("Targets", [])
    except events.exceptions.ResourceNotFoundException:
        return
    target_ids = [t["Id"] for t in targets]
    if target_ids:
        events.remove_targets(Rule=rule_name, Ids=target_ids)
    events.delete_rule(Name=rule_name)
    try:
        lam.remove_permission(FunctionName=function_name, StatementId="cordless-keepwarm")
    except lam.exceptions.ResourceNotFoundException:
        pass


def destroy(function_name, role_name, region, defer_worker=None, layer_name=None, ratelimit=False):
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

    with Spinner("keep-warm"):
        _remove_keepwarm(events, lam, function_name)

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

    if ratelimit:
        table_name = ratelimit_table_name(function_name)
        with Spinner(f"rate limit table  {table_name}"):
            dynamodb = session.client("dynamodb")
            try:
                dynamodb.delete_table(TableName=table_name)
            except dynamodb.exceptions.ResourceNotFoundException:
                pass

    print(f"  ✓ destroyed {function_name}")
