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


def build_function_zip(source_dir):
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
    return tmp.name


def ensure_iam_role(iam, role_name):
    try:
        return iam.get_role(RoleName=role_name)["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    print(f"  Creating IAM role '{role_name}'...", flush=True)
    role_arn = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=_LAMBDA_TRUST_POLICY,
    )["Role"]["Arn"]

    iam.attach_role_policy(RoleName=role_name, PolicyArn=_LAMBDA_BASIC_EXECUTION_POLICY)

    # IAM is eventually consistent — Lambda rejects a brand-new role for ~10 s
    print("  Waiting for IAM role to propagate...", flush=True)
    time.sleep(12)

    return role_arn


def _publish_cordless_layer(lam, layer_name):
    from .upload import build_layer_zip, _LAMBDA_RUNTIMES

    zip_path = build_layer_zip()
    try:
        with open(zip_path, "rb") as f:
            resp = lam.publish_layer_version(
                LayerName=layer_name,
                Content={"ZipFile": f.read()},
                CompatibleRuntimes=_LAMBDA_RUNTIMES,
            )
        return resp["LayerVersionArn"]
    finally:
        os.unlink(zip_path)


def _function_exists(lam, function_name):
    try:
        lam.get_function_configuration(FunctionName=function_name)
        return True
    except lam.exceptions.ResourceNotFoundException:
        return False


def _env_vars(env):
    return {"Variables": env} if env else {}


def _create_function(lam, function_name, zip_path, role_arn, handler, runtime, layer_arn, env):
    with open(zip_path, "rb") as f:
        lam.create_function(
            FunctionName=function_name,
            Runtime=runtime,
            Role=role_arn,
            Handler=handler,
            Code={"ZipFile": f.read()},
            Layers=[layer_arn],
            Environment=_env_vars(env),
        )
    lam.get_waiter("function_active").wait(FunctionName=function_name)


def _update_function(lam, function_name, zip_path, handler, layer_arn, env):
    with open(zip_path, "rb") as f:
        lam.update_function_code(FunctionName=function_name, ZipFile=f.read())
    lam.get_waiter("function_updated").wait(FunctionName=function_name)

    lam.update_function_configuration(
        FunctionName=function_name,
        Handler=handler,
        Layers=[layer_arn],
        Environment=_env_vars(env),
    )
    lam.get_waiter("function_updated").wait(FunctionName=function_name)


def _ensure_function_url(lam, function_name):
    try:
        return lam.get_function_url_config(FunctionName=function_name)["FunctionUrl"]
    except lam.exceptions.ResourceNotFoundException:
        pass

    url = lam.create_function_url_config(
        FunctionName=function_name,
        AuthType="NONE",
    )["FunctionUrl"]

    try:
        lam.add_permission(
            FunctionName=function_name,
            StatementId="FunctionURLAllowPublicAccess",
            Action="lambda:InvokeFunctionUrl",
            Principal="*",
            FunctionUrlAuthType="NONE",
        )
    except lam.exceptions.ResourceConflictException:
        pass  # permission already exists

    return url


def deploy(function_name, role_name, handler, source_dir, runtime, layer_name, env, region):
    if not function_name:
        raise SystemExit("Function name is required — pass --function or set [deploy] function in cordless.toml")

    from ._aws import get_session

    session = get_session(region)
    iam = session.client("iam")
    lam = session.client("lambda")

    print("Setting up IAM role...", flush=True)
    role_arn = ensure_iam_role(iam, role_name)
    print(f"  {role_arn}", flush=True)

    print("Publishing cordless layer...", flush=True)
    layer_arn = _publish_cordless_layer(lam, layer_name)
    print(f"  {layer_arn}", flush=True)

    print("Packaging function code...", flush=True)
    zip_path = build_function_zip(source_dir)

    try:
        if _function_exists(lam, function_name):
            print(f"Updating '{function_name}'...", flush=True)
            _update_function(lam, function_name, zip_path, handler, layer_arn, env)
        else:
            print(f"Creating '{function_name}'...", flush=True)
            _create_function(lam, function_name, zip_path, role_arn, handler, runtime, layer_arn, env)
    finally:
        os.unlink(zip_path)

    print("Ensuring function URL...", flush=True)
    url = _ensure_function_url(lam, function_name)
    print(f"\nDeployed. Paste this into Discord as your Interactions Endpoint URL:\n\n  {url}\n", flush=True)
