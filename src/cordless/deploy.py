import json
import os
import tempfile
import time
import zipfile

try:
    import tomllib
except ImportError:
    tomllib = None

_EXCLUDE_DIRS = {"__pycache__", ".venv", "venv", ".git", "node_modules", ".mypy_cache", ".ruff_cache"}
_EXCLUDE_FILES = {".env", "cordless.toml"}
_EXCLUDE_SUFFIXES = (".pyc", ".pyo")

_LAMBDA_TRUST_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
})
_LAMBDA_BASIC_EXECUTION_POLICY = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"


def load_config(source_dir):
    if tomllib is None:
        return {}
    path = os.path.join(source_dir, "cordless.toml")
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f).get("deploy", {})


def build_function_zip(source_dir, bundle_cordless=False, packages=None, python_version="3.12"):
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
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

        if packages:
            import subprocess, sys, shutil, os
            abi = "cp" + python_version.replace(".", "")
            # uv venvs don't ship pip — search PATH excluding the active venv
            venv = os.environ.get("VIRTUAL_ENV", "")
            search_path = os.pathsep.join(
                d for d in os.environ.get("PATH", "").split(os.pathsep)
                if not (venv and d.startswith(venv))
            )
            python = shutil.which("python3", path=search_path) or shutil.which("python", path=search_path) or sys.executable
            with tempfile.TemporaryDirectory() as pkg_tmp:
                subprocess.run(
                    [
                        python, "-m", "pip", "install",
                        "--target", pkg_tmp,
                        "--platform", "manylinux2014_x86_64",
                        "--python-version", python_version,
                        "--implementation", "cp",
                        "--abi", abi,
                        "--only-binary", ":all:",
                        "--no-compile",
                        *packages,
                    ],
                    check=True,
                )
                for root, dirs, files in os.walk(pkg_tmp):
                    dirs[:] = [d for d in dirs if d != "__pycache__"]
                    for fname in files:
                        if fname.endswith(".pyc"):
                            continue
                        abs_path = os.path.join(root, fname)
                        zf.write(abs_path, os.path.relpath(abs_path, pkg_tmp))

    return tmp.name


def ensure_iam_role(iam, role_name):
    try:
        return iam.get_role(RoleName=role_name)["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    role_arn = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=_LAMBDA_TRUST_POLICY,
    )["Role"]["Arn"]

    iam.attach_role_policy(RoleName=role_name, PolicyArn=_LAMBDA_BASIC_EXECUTION_POLICY)

    # IAM is eventually consistent — Lambda rejects a brand-new role for ~10 s
    time.sleep(12)

    return role_arn


def _cordless_version():
    from importlib.metadata import version
    return version("cordless")


def _publish_cordless_layer(lam, layer_name):
    from .upload import build_layer_zip, _LAMBDA_RUNTIMES

    current_version = _cordless_version()
    description = f"cordless {current_version}"

    # Reuse the existing layer version if it was built from the same cordless version
    try:
        versions = lam.list_layer_versions(LayerName=layer_name).get("LayerVersions", [])
        for v in versions:
            if v.get("Description") == description:
                return v["LayerVersionArn"]
    except lam.exceptions.ResourceNotFoundException:
        pass

    zip_path = build_layer_zip()
    try:
        with open(zip_path, "rb") as f:
            resp = lam.publish_layer_version(
                LayerName=layer_name,
                Description=description,
                Content={"ZipFile": f.read()},
                CompatibleRuntimes=_LAMBDA_RUNTIMES,
            )
        return resp["LayerVersionArn"]
    finally:
        os.unlink(zip_path)


def _function_exists(lam, function_name):
    try:
        config = lam.get_function_configuration(FunctionName=function_name)
        return True, config["FunctionArn"]
    except lam.exceptions.ResourceNotFoundException:
        return False, None


def _env_vars(env):
    return {"Variables": env} if env else {}


def _create_function(lam, function_name, zip_path, role_arn, handler, runtime, layer_arn, env, timeout=10):
    with open(zip_path, "rb") as f:
        resp = lam.create_function(
            FunctionName=function_name,
            Runtime=runtime,
            Role=role_arn,
            Handler=handler,
            Code={"ZipFile": f.read()},
            Layers=[layer_arn] if layer_arn else [],
            Environment=_env_vars(env),
            Timeout=timeout,
        )
    lam.get_waiter("function_active").wait(FunctionName=function_name)
    return resp["FunctionArn"]


def _update_function(lam, function_name, zip_path, handler, layer_arn, env, timeout=10):
    with open(zip_path, "rb") as f:
        lam.update_function_code(FunctionName=function_name, ZipFile=f.read())
    lam.get_waiter("function_updated").wait(FunctionName=function_name)

    lam.update_function_configuration(
        FunctionName=function_name,
        Handler=handler,
        Layers=[layer_arn] if layer_arn else [],
        Environment=_env_vars(env),
        Timeout=timeout,
    )
    lam.get_waiter("function_updated").wait(FunctionName=function_name)


def _ensure_api_gateway(apigw, lam, function_name, function_arn, region, account_id):
    api_name = f"{function_name}-api"

    # Reuse existing API if one with this name exists
    apis = apigw.get_apis().get("Items", [])
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

    return f"{endpoint}/"


def _allow_worker_invoke(iam, role_name, worker_arn):
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="cordless-worker-invoke",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "lambda:InvokeFunction",
                "Resource": worker_arn,
            }],
        }),
    )


def deploy(function_name, role_name, handler, source_dir, runtime, layer_name, env, region,
           timeout=10, bundle_cordless=False, packages=None, python_version="3.12",
           defer_worker=None, defer_handler="lambda_function.worker_handler", defer_timeout=30):
    if not function_name:
        raise SystemExit("Function name is required — pass --function or set [deploy] function in cordless.toml")

    from ._aws import get_session
    from ._progress import Spinner, success

    session = get_session(region)
    iam = session.client("iam")
    lam = session.client("lambda")
    apigw = session.client("apigatewayv2")
    account_id = session.client("sts").get_caller_identity()["Account"]

    print()

    with Spinner("IAM role"):
        role_arn = ensure_iam_role(iam, role_name)

    if bundle_cordless:
        layer_arn = None
    else:
        with Spinner("cordless layer"):
            layer_arn = _publish_cordless_layer(lam, layer_name)

    with Spinner("packaging"):
        zip_path = build_function_zip(source_dir, bundle_cordless=bundle_cordless, packages=packages, python_version=python_version)

    try:
        exists, function_arn = _function_exists(lam, function_name)
        verb = "updating" if exists else "creating"
        with Spinner(f"{verb}  {function_name}"):
            if exists:
                _update_function(lam, function_name, zip_path, handler, layer_arn or "", env, timeout=timeout)
            else:
                function_arn = _create_function(lam, function_name, zip_path, role_arn, handler, runtime, layer_arn or "", env, timeout=timeout)

        with Spinner("API Gateway"):
            url = _ensure_api_gateway(apigw, lam, function_name, function_arn, region, account_id)

        if defer_worker:
            w_exists, worker_arn = _function_exists(lam, defer_worker)
            w_verb = "updating" if w_exists else "creating"
            with Spinner(f"{w_verb}  {defer_worker}"):
                if w_exists:
                    _update_function(lam, defer_worker, zip_path, defer_handler, layer_arn, {}, timeout=defer_timeout)
                else:
                    worker_arn = _create_function(lam, defer_worker, zip_path, role_arn, defer_handler, runtime, layer_arn, {}, timeout=defer_timeout)
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

    success(url)
