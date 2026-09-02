"""Raw HTTP route matching and response coercion for `@bot.route` handlers.

These routes sit outside the Discord interaction flow. A request arrives on
the same Lambda, skips signature verification, and the handler receives the
raw event dict together with the bot instance.
"""

import base64
import json
import re
from typing import Any, cast

_Pattern = list[tuple[str, str]]

_PARAM_NAME = re.compile(r"[A-Za-z0-9._]+")
_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

_JSON_CONTENT_TYPE = "application/json"
_TEXT_CONTENT_TYPE = "text/plain; charset=utf-8"
_BINARY_CONTENT_TYPE = "application/octet-stream"


def normalize_path(path: str) -> str:
    """Return `path` with a leading slash, single slashes between segments,
    and no trailing slash except for the root."""
    segments = [s for s in path.split("/") if s]
    return "/" + "/".join(segments)


def normalize(method: str, path: str) -> tuple[str, str]:
    """Validate a route and return its canonical `(method, path)` pair.

    Raises `ValueError` for an unknown method, a malformed `{name}` segment,
    or the `POST /` route, which is reserved for Discord's interaction
    endpoint.
    """
    method = method.upper()
    if method not in _METHODS:
        raise ValueError(f"Unknown HTTP method {method!r}: expected one of {', '.join(sorted(_METHODS))}")

    norm = normalize_path(path)
    segments = [s for s in norm.split("/") if s]
    for index, segment in enumerate(segments):
        if segment.startswith("{") and segment.endswith("}"):
            name = segment[1:-1]
            greedy = name.endswith("+")
            if greedy:
                name = name[:-1]
                if index != len(segments) - 1:
                    raise ValueError(f"Greedy parameter {segment!r} in {path!r} must be the final segment")
            if not _PARAM_NAME.fullmatch(name):
                raise ValueError(f"Invalid path parameter {segment!r} in {path!r}")
        elif "{" in segment or "}" in segment:
            raise ValueError(
                f"Invalid path segment {segment!r} in {path!r}: a parameter must be a whole segment like {{id}}"
            )

    if (method, norm) == ("POST", "/"):
        raise ValueError("POST / is reserved for Discord's interaction endpoint")
    return method, norm


def compile_pattern(norm_path: str) -> _Pattern:
    """Turn a normalised path into a list of match segments, each a
    `("lit", value)`, `("param", name)`, or `("greedy", name)` tuple."""
    pattern: _Pattern = []
    for segment in (s for s in norm_path.split("/") if s):
        if segment.startswith("{") and segment.endswith("}"):
            name = segment[1:-1]
            if name.endswith("+"):
                pattern.append(("greedy", name[:-1]))
            else:
                pattern.append(("param", name))
        else:
            pattern.append(("lit", segment))
    return pattern


def match_pattern(pattern: _Pattern, path: str) -> dict[str, str] | None:
    """Return a `{name: value}` dict when `path` matches `pattern`, else
    `None`. A greedy segment captures the rest of the path verbatim."""
    parts = [p for p in path.split("/") if p]
    params: dict[str, str] = {}
    for index, (kind, value) in enumerate(pattern):
        if kind == "greedy":
            if index >= len(parts):
                return None
            params[value] = "/".join(parts[index:])
            return params
        if index >= len(parts):
            return None
        if kind == "lit":
            if parts[index] != value:
                return None
        else:
            params[value] = parts[index]
    if len(parts) != len(pattern):
        return None
    return params


def patterns_conflict(a: _Pattern, b: _Pattern) -> bool:
    """True when two patterns would match the same set of paths, so only one
    can be registered. Parameter names are ignored; literal values are not."""
    if len(a) != len(b):
        return False
    for (kind_a, value_a), (kind_b, value_b) in zip(a, b):
        if kind_a != kind_b:
            return False
        if kind_a == "lit" and value_a != value_b:
            return False
    return True


def specificity(pattern: _Pattern) -> tuple[int, int, bool]:
    """Sort key placing more literal, longer, non-greedy patterns first, so
    a static route always wins over one with a parameter in the same slot."""
    literals = sum(1 for kind, _ in pattern if kind == "lit")
    has_greedy = any(kind == "greedy" for kind, _ in pattern)
    return (literals, len(pattern), not has_greedy)


def request_method_path(event: dict[str, Any]) -> tuple[str | None, str | None]:
    """Pull the HTTP method and path from a Lambda event.

    Handles the API Gateway v2 shape (`requestContext.http`), the v1 shape
    (`httpMethod` / `path`), and the local dev server. Returns
    `(None, None)` for a bare interaction invoke that carries no HTTP
    envelope.
    """
    request_context: Any = event.get("requestContext") or {}
    http: Any = request_context.get("http") or {}
    method: Any = http.get("method") or event.get("httpMethod")
    path: Any = http.get("path") or event.get("rawPath") or event.get("path")
    if method is None or path is None:
        return None, None
    return method.upper(), normalize_path(path)


def build_response(returned: Any) -> dict[str, Any]:
    """Coerce a route handler's return value into a Lambda proxy response.

    Accepts a full proxy dict (passed through unchanged), a status int, a
    string, a bytes body, a JSON serialisable dict or list, or a
    `(status, body)` or `(status, body, headers)` tuple.
    """
    if isinstance(returned, dict) and "statusCode" in returned:
        return cast("dict[str, Any]", returned)

    headers: Any = {}
    if isinstance(returned, tuple):
        returned = cast("tuple[Any, ...]", returned)
        if len(returned) == 2:
            status, body = returned
        elif len(returned) == 3:
            status, body, headers = returned
        else:
            raise ValueError(
                f"A route handler tuple must be (status, body) or (status, body, headers), got {len(returned)} items"
            )
    elif isinstance(returned, bool):
        raise ValueError(f"A route handler cannot return a bool ({returned!r}); return an int, str, dict, or tuple")
    elif isinstance(returned, int):
        status, body = returned, None
    else:
        status, body = 200, cast("Any", returned)

    return _finish(status, body, dict(headers or {}))


def _finish(status: int, body: Any, headers: dict[str, str]) -> dict[str, Any]:
    is_base64 = False
    if body is None:
        out_body = ""
    elif isinstance(body, (bytes, bytearray)):
        out_body = base64.b64encode(bytes(body)).decode()
        is_base64 = True
        headers.setdefault("Content-Type", _BINARY_CONTENT_TYPE)
    elif isinstance(body, str):
        out_body = body
        headers.setdefault("Content-Type", _TEXT_CONTENT_TYPE)
    elif isinstance(body, (dict, list)):
        out_body = json.dumps(body)
        headers.setdefault("Content-Type", _JSON_CONTENT_TYPE)
    else:
        out_body = str(body)
        headers.setdefault("Content-Type", _TEXT_CONTENT_TYPE)

    response: dict[str, Any] = {"statusCode": status, "headers": headers, "body": out_body}
    if is_base64:
        response["isBase64Encoded"] = True
    return response
