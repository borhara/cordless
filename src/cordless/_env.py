"""Shared .env parsing/loading, with optional per-environment overlay files."""

import os

ENV_VAR = "ENV"


def resolve_environment(explicit=None):
    """CLI flag wins over $ENV; neither means no overlay file."""
    return explicit or os.environ.get(ENV_VAR)


def _parse_env_file(path):
    result = {}
    if not os.path.exists(path):
        return result
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip().strip("\"'")
    return result


def read_dotenv(source_dir, environment=None):
    """Return .env merged with .env.<environment>, the latter taking priority. Missing files are skipped."""
    result = _parse_env_file(os.path.join(source_dir, ".env"))
    if environment:
        result.update(_parse_env_file(os.path.join(source_dir, f".env.{environment}")))
    return result


def load_dotenv(source_dir, environment=None):
    """Load .env (+ .env.<environment> override) into the process environment (no clobber)."""
    for key, value in read_dotenv(source_dir, environment).items():
        os.environ.setdefault(key, value)
