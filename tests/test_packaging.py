"""Deploy packaging: zip contents, excludes, config loading, package cache keys."""
import os
import zipfile

from cordless.deploy import _packages_cache_dir, build_function_zip, load_config


def _zip_names(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        return set(zf.namelist())


def _make_tree(root, paths):
    for p in paths:
        full = root / p
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("x")


def test_zip_includes_source_files(tmp_path):
    _make_tree(tmp_path, ["lambda_function.py", "cogs/shop.py"])
    zip_path = build_function_zip(str(tmp_path))
    try:
        assert _zip_names(zip_path) == {"lambda_function.py", "cogs/shop.py"}
    finally:
        os.unlink(zip_path)


def test_zip_excludes_junk(tmp_path):
    _make_tree(tmp_path, [
        "lambda_function.py",
        ".env",
        "cordless.toml",
        ".DS_Store",
        "app.pyc",
        "__pycache__/app.cpython-312.pyc",
        "mybot.egg-info/PKG-INFO",
        ".pytest_cache/x",
        ".venv/lib/thing.py",
        "dist/pkg.whl",
        "build/lib/x.py",
        "node_modules/pkg/index.js",
    ])
    zip_path = build_function_zip(str(tmp_path))
    try:
        assert _zip_names(zip_path) == {"lambda_function.py"}
    finally:
        os.unlink(zip_path)


def test_load_config_reads_deploy_table(tmp_path):
    (tmp_path / "cordless.toml").write_text(
        '[deploy]\nfunction = "my-bot"\ntimeout = 0\n\n[deploy.env]\nKEY = "value"\n'
    )
    cfg = load_config(str(tmp_path))
    assert cfg["function"] == "my-bot"
    assert cfg["timeout"] == 0  # falsy values must survive
    assert cfg["env"] == {"KEY": "value"}


def test_load_config_missing_file_returns_empty(tmp_path):
    assert load_config(str(tmp_path)) == {}


def test_packages_cache_key_is_deterministic():
    a = _packages_cache_dir(["pillow", "requests"], "3.12")
    b = _packages_cache_dir(["requests", "pillow"], "3.12")  # order-insensitive
    assert a == b


def test_packages_cache_key_varies_by_inputs():
    base = _packages_cache_dir(["pillow"], "3.12")
    assert _packages_cache_dir(["pillow"], "3.13") != base
    assert _packages_cache_dir(["pillow>=10"], "3.12") != base


# --- bundle_cordless dist-info ---

def test_bundle_cordless_includes_dist_info(tmp_path, monkeypatch):
    import cordless.deploy

    pkg_root = tmp_path / "site-packages"
    pkg_dir = pkg_root / "cordless"
    dist_info = pkg_root / "cordless-1.0.0b2.dist-info"
    _make_tree(pkg_dir, ["app.py", "__init__.py"])
    _make_tree(dist_info, ["METADATA", "RECORD"])

    monkeypatch.setattr(cordless.deploy, "_ensure_packages", lambda pkgs, v: str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir(exist_ok=True)

    import cordless.upload
    monkeypatch.setattr(cordless.upload, "_cordless_package_dir", lambda: str(pkg_dir))

    src = tmp_path / "src"
    src.mkdir()
    (src / "lambda_function.py").write_text("x")

    zip_path = cordless.deploy.build_function_zip(str(src), bundle_cordless=True)
    try:
        names = _zip_names(zip_path)
        assert "cordless-1.0.0b2.dist-info/METADATA" in names
        assert "cordless-1.0.0b2.dist-info/RECORD" in names
    finally:
        os.unlink(zip_path)


def test_bundle_cordless_includes_egg_info(tmp_path, monkeypatch):
    import cordless.deploy

    pkg_root = tmp_path / "site-packages"
    pkg_dir = pkg_root / "cordless"
    egg_info = pkg_root / "cordless.egg-info"
    _make_tree(pkg_dir, ["app.py", "__init__.py"])
    _make_tree(egg_info, ["PKG-INFO", "top_level.txt"])

    monkeypatch.setattr(cordless.deploy, "_ensure_packages", lambda pkgs, v: str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir(exist_ok=True)

    import cordless.upload
    monkeypatch.setattr(cordless.upload, "_cordless_package_dir", lambda: str(pkg_dir))

    src = tmp_path / "src"
    src.mkdir()
    (src / "lambda_function.py").write_text("x")

    zip_path = cordless.deploy.build_function_zip(str(src), bundle_cordless=True)
    try:
        names = _zip_names(zip_path)
        assert "cordless.egg-info/PKG-INFO" in names
    finally:
        os.unlink(zip_path)


# --- layer zip ---

def test_layer_zip_bundles_pynacl_extras(tmp_path, monkeypatch):
    import cordless.upload

    extras = tmp_path / "extras"
    _make_tree(extras, ["nacl/signing.py", "nacl/_sodium.abi3.so"])
    monkeypatch.setattr(cordless.upload, "_layer_extras_dir", lambda v: str(extras))

    zip_path = cordless.upload.build_layer_zip("3.12")
    try:
        names = _zip_names(zip_path)
        assert "python/nacl/signing.py" in names
        assert "python/nacl/_sodium.abi3.so" in names
        assert any(n.startswith("python/cordless/") for n in names)
    finally:
        os.unlink(zip_path)


def test_layer_zip_survives_pynacl_fetch_failure(monkeypatch):
    import cordless.upload

    monkeypatch.setattr(cordless.upload, "_layer_extras_dir", lambda v: None)

    zip_path = cordless.upload.build_layer_zip("3.12")
    try:
        names = _zip_names(zip_path)
        assert any(n.startswith("python/cordless/") for n in names)
        assert not any("/nacl/" in n for n in names)
    finally:
        os.unlink(zip_path)


def test_layer_zip_without_runtime_skips_extras(monkeypatch):
    import cordless.upload

    called = []
    monkeypatch.setattr(cordless.upload, "_layer_extras_dir", lambda v: called.append(v))

    zip_path = cordless.upload.build_layer_zip()
    try:
        assert called == []
    finally:
        os.unlink(zip_path)


def test_layer_zip_includes_dist_info(tmp_path, monkeypatch):
    import cordless.upload

    site_dir = tmp_path / "site-packages"
    pkg_dir = site_dir / "cordless"
    dist_info = site_dir / "cordless-1.0.0b2.dist-info"
    _make_tree(pkg_dir, ["app.py", "__init__.py"])
    _make_tree(dist_info, ["METADATA", "RECORD"])

    monkeypatch.setattr(cordless.upload, "_cordless_package_dir", lambda: str(pkg_dir))
    monkeypatch.setattr(cordless.upload, "_layer_extras_dir", lambda v: None)

    zip_path = cordless.upload.build_layer_zip("3.12")
    try:
        names = _zip_names(zip_path)
        assert "python/cordless-1.0.0b2.dist-info/METADATA" in names
        assert "python/cordless-1.0.0b2.dist-info/RECORD" in names
        assert "python/cordless/app.py" in names
    finally:
        os.unlink(zip_path)
