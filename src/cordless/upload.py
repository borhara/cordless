import importlib.util
import json
import os
import subprocess
import tempfile
import zipfile

_LAMBDA_RUNTIMES = ["python3.10", "python3.11", "python3.12", "python3.13"]


def _require_aws_cli():
    result = subprocess.run(["aws", "--version"], capture_output=True)
    if result.returncode != 0:
        raise SystemExit(
            "AWS CLI not found. Install it: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        )


def _cordless_package_dir():
    spec = importlib.util.find_spec("cordless")
    if spec is None or spec.origin is None:
        raise SystemExit("Cannot locate the cordless package — is it installed?")
    return os.path.dirname(spec.origin)


def build_layer_zip():
    """Zip the cordless package in the python/ layout required by Lambda layers."""
    pkg_dir = _cordless_package_dir()
    site_dir = os.path.dirname(pkg_dir)  # the directory that contains the cordless/ folder

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(pkg_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fname in files:
                if fname.endswith(".pyc"):
                    continue
                abs_path = os.path.join(root, fname)
                # python/cordless/... matches Lambda layer layout
                rel_path = os.path.relpath(abs_path, site_dir)
                zf.write(abs_path, os.path.join("python", rel_path))

    return tmp.name


def _aws(args, error_prefix):
    result = subprocess.run(["aws"] + args + ["--output", "json"], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"{error_prefix}:\n{result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def publish_layer(zip_path, layer_name, region):
    cmd = [
        "lambda", "publish-layer-version",
        "--layer-name", layer_name,
        "--zip-file", f"fileb://{zip_path}",
        "--compatible-runtimes", *_LAMBDA_RUNTIMES,
    ]
    if region:
        cmd += ["--region", region]
    return _aws(cmd, "Failed to publish layer")


def attach_layer(function_name, layer_arn, layer_name, region):
    """Attach the new layer version to the function, replacing any older cordless layer."""
    get_cmd = ["lambda", "get-function-configuration", "--function-name", function_name]
    if region:
        get_cmd += ["--region", region]
    config = _aws(get_cmd, f"Failed to get configuration for function '{function_name}'")

    existing = [layer["Arn"] for layer in config.get("Layers", [])]
    # Drop any previous version of this layer by name
    kept = [arn for arn in existing if f":layer:{layer_name}:" not in arn]
    new_layers = kept + [layer_arn]

    update_cmd = [
        "lambda", "update-function-configuration",
        "--function-name", function_name,
        "--layers", *new_layers,
    ]
    if region:
        update_cmd += ["--region", region]
    _aws(update_cmd, f"Failed to update function '{function_name}'")


def upload(function_name, layer_name, region):
    _require_aws_cli()

    print("Building layer zip...", flush=True)
    zip_path = build_layer_zip()

    try:
        print(f"Publishing layer '{layer_name}'...", flush=True)
        info = publish_layer(zip_path, layer_name, region)
        layer_arn = info["LayerVersionArn"]
        print(f"  {layer_arn}", flush=True)

        print(f"Attaching to '{function_name}'...", flush=True)
        attach_layer(function_name, layer_arn, layer_name, region)
        print("Done.", flush=True)
    finally:
        os.unlink(zip_path)
