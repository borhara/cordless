import importlib.util
import os
import tempfile
import zipfile

_LAMBDA_RUNTIMES = ["python3.10", "python3.11", "python3.12", "python3.13"]


def _cordless_package_dir():
    spec = importlib.util.find_spec("cordless")
    if spec is None or spec.origin is None:
        raise SystemExit("Cannot locate the cordless package. Is it installed?")
    return os.path.dirname(spec.origin)


def _layer_extras_dir(python_version):
    """Fetch cordless dependencies (httpx, pynacl) for the layer."""
    from .deploy import _ensure_packages
    try:
        return _ensure_packages(["httpx", "pynacl"], python_version)
    except Exception as exc:
        print(f"  (layer extras unavailable, falling back: {exc})")
        return None


def build_layer_zip(python_version=None):
    """Zip cordless (plus pynacl, when fetchable) in the python/ layout Lambda layers require."""
    pkg_dir = _cordless_package_dir()
    site_dir = os.path.dirname(pkg_dir)

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(pkg_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fname in files:
                if fname.endswith(".pyc"):
                    continue
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, site_dir)
                zf.write(abs_path, os.path.join("python", rel_path))

        extras_dir = _layer_extras_dir(python_version) if python_version else None
        if extras_dir:
            for root, dirs, files in os.walk(extras_dir):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for fname in files:
                    if fname.endswith(".pyc"):
                        continue
                    abs_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(abs_path, extras_dir)
                    zf.write(abs_path, os.path.join("python", rel_path))

    return tmp.name


def upload(function_name, layer_name, region, python_version=None):
    from ._aws import get_session

    session = get_session(region)
    lam = session.client("lambda")

    print("Building layer zip...", flush=True)
    zip_path = build_layer_zip(python_version)

    try:
        print(f"Publishing layer '{layer_name}'...", flush=True)
        with open(zip_path, "rb") as f:
            resp = lam.publish_layer_version(
                LayerName=layer_name,
                Content={"ZipFile": f.read()},
                CompatibleRuntimes=[f"python{python_version}"] if python_version else _LAMBDA_RUNTIMES,
            )
        layer_arn = resp["LayerVersionArn"]
        print(f"  {layer_arn}", flush=True)

        print(f"Attaching to '{function_name}'...", flush=True)
        config = lam.get_function_configuration(FunctionName=function_name)
        existing = [layer["Arn"] for layer in config.get("Layers", [])]
        kept = [arn for arn in existing if f":layer:{layer_name}:" not in arn]

        lam.update_function_configuration(
            FunctionName=function_name,
            Layers=kept + [layer_arn],
        )
        print("Done.", flush=True)
    finally:
        os.unlink(zip_path)
