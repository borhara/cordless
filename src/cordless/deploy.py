import json
import os
import subprocess
import tempfile
import zipfile

try:
    import tomllib
except ImportError:
    tomllib = None

_EXCLUDE_DIRS = {"__pycache__", ".venv", "venv", ".git", "node_modules", ".mypy_cache", ".ruff_cache"}
_EXCLUDE_FILES = {".env"}
_EXCLUDE_SUFFIXES = (".pyc", ".pyo")


def load_config(source_dir):
    """Read cordless.toml from source_dir if present and tomllib is available."""
    if tomllib is None:
        return {}

    path = os.path.join(source_dir, "cordless.toml")
    if not os.path.exists(path):
        return {}

    with open(path, "rb") as f:
        return tomllib.load(f).get("deploy", {})


def build_function_zip(source_dir):
    """Zip the user's source directory for Lambda deployment."""
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
            for fname in files:
                if fname in _EXCLUDE_FILES or fname.endswith(_EXCLUDE_SUFFIXES):
                    continue
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, source_dir)
                zf.write(abs_path, rel_path)

    return tmp.name


def _aws(args, error_prefix, allow_fail=False):
    result = subprocess.run(
        ["aws"] + args + ["--output", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if allow_fail:
            return None
        raise SystemExit(f"{error_prefix}:\n{result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _region_args(region):
    return ["--region", region] if region else []


def _publish_cordless_layer(layer_name, region):
    from .upload import build_layer_zip

    zip_path = build_layer_zip()
    try:
        from .upload import _LAMBDA_RUNTIMES
        cmd = [
            "lambda", "publish-layer-version",
            "--layer-name", layer_name,
            "--zip-file", f"fileb://{zip_path}",
            "--compatible-runtimes", *_LAMBDA_RUNTIMES,
        ] + _region_args(region)
        info = _aws(cmd, "Failed to publish cordless layer")
        return info["LayerVersionArn"]
    finally:
        os.unlink(zip_path)


def _function_exists(function_name, region):
    result = _aws(
        ["lambda", "get-function-configuration", "--function-name", function_name] + _region_args(region),
        "",
        allow_fail=True,
    )
    return result is not None


def _env_vars_arg(env):
    if not env:
        return []
    pairs = ",".join(f"{k}={v}" for k, v in env.items())
    return ["--environment", f"Variables={{{pairs}}}"]


def _wait_for_update(function_name, region):
    _aws(
        ["lambda", "wait", "function-updated", "--function-name", function_name] + _region_args(region),
        f"Timed out waiting for '{function_name}' to finish updating",
    )


def create_function(function_name, zip_path, role, handler, runtime, layer_arn, env, region):
    cmd = [
        "lambda", "create-function",
        "--function-name", function_name,
        "--runtime", runtime,
        "--role", role,
        "--handler", handler,
        "--zip-file", f"fileb://{zip_path}",
        "--layers", layer_arn,
    ] + _env_vars_arg(env) + _region_args(region)
    return _aws(cmd, f"Failed to create function '{function_name}'")


def update_function(function_name, zip_path, handler, layer_arn, env, region):
    _aws(
        ["lambda", "update-function-code", "--function-name", function_name, "--zip-file", f"fileb://{zip_path}"]
        + _region_args(region),
        f"Failed to update code for '{function_name}'",
    )
    _wait_for_update(function_name, region)

    cmd = [
        "lambda", "update-function-configuration",
        "--function-name", function_name,
        "--handler", handler,
        "--layers", layer_arn,
    ] + _env_vars_arg(env) + _region_args(region)
    _aws(cmd, f"Failed to update configuration for '{function_name}'")
    _wait_for_update(function_name, region)


def ensure_function_url(function_name, region):
    """Return existing function URL or create one (NONE auth, for Discord signed requests)."""
    info = _aws(
        ["lambda", "get-function-url-config", "--function-name", function_name] + _region_args(region),
        "",
        allow_fail=True,
    )
    if info:
        return info["FunctionUrl"]

    info = _aws(
        ["lambda", "create-function-url-config", "--function-name", function_name, "--auth-type", "NONE"]
        + _region_args(region),
        f"Failed to create function URL for '{function_name}'",
    )

    # Allow public access via resource-based policy
    _aws(
        [
            "lambda", "add-permission",
            "--function-name", function_name,
            "--statement-id", "FunctionURLAllowPublicAccess",
            "--action", "lambda:InvokeFunctionUrl",
            "--principal", "*",
            "--function-url-auth-type", "NONE",
        ] + _region_args(region),
        "",
        allow_fail=True,  # permission may already exist
    )

    return info["FunctionUrl"]


def deploy(function_name, role, handler, source_dir, runtime, layer_name, env, region):
    if not function_name:
        raise SystemExit("Function name is required — pass --function or set [deploy] function in cordless.toml")

    from .upload import _require_aws_cli
    _require_aws_cli()

    print("Publishing cordless layer...", flush=True)
    layer_arn = _publish_cordless_layer(layer_name, region)
    print(f"  {layer_arn}", flush=True)

    print("Packaging function code...", flush=True)
    zip_path = build_function_zip(source_dir)

    try:
        exists = _function_exists(function_name, region)

        if exists:
            print(f"Updating '{function_name}'...", flush=True)
            update_function(function_name, zip_path, handler, layer_arn, env, region)
        else:
            if not role:
                raise SystemExit("--role is required when creating a new function")
            print(f"Creating '{function_name}'...", flush=True)
            create_function(function_name, zip_path, role, handler, runtime, layer_arn, env, region)
    finally:
        os.unlink(zip_path)

    print("Ensuring function URL...", flush=True)
    url = ensure_function_url(function_name, region)
    print(f"\nDeployed. Set this as your Discord Interactions Endpoint URL:\n\n  {url}\n", flush=True)
