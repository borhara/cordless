import json
from asyncio import run

import pytest

from cordless import Cog
from cordless.app import Cordless
from cordless.errors import CordlessError
from cordless.routes import (
    build_response,
    compile_pattern,
    match_pattern,
    normalize,
    request_method_path,
)
from cordless.testing import invoke_route


def _event(method, path, *, body="", headers=None, query=None):
    return {
        "body": body,
        "headers": headers or {},
        "rawPath": path,
        "rawQueryString": "",
        "queryStringParameters": query,
        "requestContext": {"http": {"method": method, "path": path}},
        "isBase64Encoded": False,
    }


# --- normalize ---


def test_normalize_adds_leading_slash_and_trims_trailing():
    assert normalize("get", "healthz/") == ("GET", "/healthz")


def test_normalize_collapses_repeated_slashes():
    assert normalize("GET", "//a///b/") == ("GET", "/a/b")


def test_normalize_rejects_unknown_method():
    with pytest.raises(ValueError, match="Unknown HTTP method"):
        normalize("FETCH", "/x")


def test_normalize_rejects_post_root():
    with pytest.raises(ValueError, match="reserved for Discord"):
        normalize("POST", "/")


def test_normalize_rejects_partial_parameter_segment():
    with pytest.raises(ValueError, match="whole segment"):
        normalize("GET", "/users/u{id}")


def test_normalize_rejects_greedy_before_final_segment():
    with pytest.raises(ValueError, match="final segment"):
        normalize("GET", "/files/{rest+}/meta")


# --- pattern matching ---


def test_match_pattern_exact():
    assert match_pattern(compile_pattern("/a/b"), "/a/b") == {}
    assert match_pattern(compile_pattern("/a/b"), "/a/c") is None


def test_match_pattern_captures_param():
    assert match_pattern(compile_pattern("/gh/{repo}/hook"), "/gh/cordless/hook") == {"repo": "cordless"}


def test_match_pattern_length_mismatch():
    assert match_pattern(compile_pattern("/a/{x}"), "/a/b/c") is None
    assert match_pattern(compile_pattern("/a/{x}"), "/a") is None


def test_match_pattern_greedy_captures_remainder():
    assert match_pattern(compile_pattern("/files/{rest+}"), "/files/a/b/c") == {"rest": "a/b/c"}
    assert match_pattern(compile_pattern("/files/{rest+}"), "/files") is None


def test_root_pattern_matches_root():
    assert match_pattern(compile_pattern("/"), "/") == {}


# --- request_method_path ---


def test_request_method_path_v2_shape():
    assert request_method_path({"requestContext": {"http": {"method": "post", "path": "/x/"}}}) == ("POST", "/x")


def test_request_method_path_v1_shape():
    assert request_method_path({"httpMethod": "GET", "path": "/x"}) == ("GET", "/x")


def test_request_method_path_bare_interaction():
    assert request_method_path({"body": "{}"}) == (None, None)


# --- build_response ---


def test_build_response_passes_through_proxy_dict():
    proxy = {"statusCode": 201, "headers": {}, "body": "ok"}
    assert build_response(proxy) is proxy


def test_build_response_string():
    r = build_response("hello")
    assert r["statusCode"] == 200
    assert r["body"] == "hello"
    assert r["headers"]["Content-Type"].startswith("text/plain")


def test_build_response_dict_is_json():
    r = build_response({"ok": True})
    assert r["headers"]["Content-Type"] == "application/json"
    assert json.loads(r["body"]) == {"ok": True}


def test_build_response_bare_int_is_status():
    r = build_response(204)
    assert r["statusCode"] == 204
    assert r["body"] == ""


def test_build_response_none_is_empty_200():
    r = build_response(None)
    assert r["statusCode"] == 200
    assert r["body"] == ""


def test_build_response_status_body_tuple():
    r = build_response((418, "teapot"))
    assert r["statusCode"] == 418
    assert r["body"] == "teapot"


def test_build_response_status_body_headers_tuple():
    r = build_response((302, "", {"Location": "https://example.com"}))
    assert r["statusCode"] == 302
    assert r["headers"]["Location"] == "https://example.com"


def test_build_response_bytes_is_base64():
    r = build_response(b"\x00\x01\x02")
    assert r["isBase64Encoded"] is True
    assert r["headers"]["Content-Type"] == "application/octet-stream"


def test_build_response_rejects_bool():
    with pytest.raises(ValueError, match="cannot return a bool"):
        build_response(True)


def test_build_response_rejects_wrong_tuple_length():
    with pytest.raises(ValueError, match="must be"):
        build_response((1, 2, 3, 4))


# --- registration ---


def test_route_registration_conflict_raises():
    bot = Cordless()

    @bot.route("GET", "/gh/{repo}/hook")
    async def a(event, bot):
        return "a"

    with pytest.raises(ValueError, match="conflicts with"):

        @bot.route("GET", "/gh/{name}/hook")
        async def b(event, bot):
            return "b"


def test_route_registration_rejects_post_root():
    bot = Cordless()
    with pytest.raises(ValueError, match="reserved for Discord"):

        @bot.route("POST", "/")
        async def a(event, bot):
            return "a"


def test_route_defs_sorted_with_tokens_intact():
    bot = Cordless()

    @bot.route("POST", "/stripe/webhook")
    async def a(event, bot):
        return ""

    @bot.route("GET", "/gh/{repo}/hook")
    async def b(event, bot):
        return ""

    assert bot.router.route_defs() == [("GET", "/gh/{repo}/hook"), ("POST", "/stripe/webhook")]


# --- dispatch through handle() ---


def test_handle_dispatches_route():
    bot = Cordless()

    @bot.route("POST", "/stripe/webhook")
    async def hook(event, received_bot):
        assert received_bot is bot
        return {"got": json.loads(event["body"])["id"]}

    result = bot.handle(_event("POST", "/stripe/webhook", body='{"id": "evt_1"}'))
    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == {"got": "evt_1"}


def test_handle_passes_path_params():
    bot = Cordless()
    seen = {}

    @bot.route("GET", "/gh/{repo}/hook")
    async def hook(event, bot):
        seen.update(event["pathParameters"])
        return 204

    result = bot.handle(_event("GET", "/gh/cordless/hook"))
    assert result["statusCode"] == 204
    assert seen == {"repo": "cordless"}


def test_handle_unmatched_route_is_404():
    bot = Cordless()

    @bot.route("GET", "/healthz")
    async def health(event, bot):
        return "ok"

    result = bot.handle(_event("GET", "/nope"))
    assert result["statusCode"] == 404


def test_handle_still_routes_discord_interaction_on_post_root():
    bot = Cordless()

    @bot.route("GET", "/healthz")
    async def health(event, bot):
        return "ok"

    @bot.command("ping")
    async def ping(ctx):
        return await ctx.send("pong")

    result = bot.handle({"body": json.dumps({"type": 2, "data": {"name": "ping"}})})
    assert json.loads(result["body"])["data"]["content"] == "pong"


def test_handle_routes_discord_interaction_on_non_root_post_path():
    bot = Cordless()

    @bot.route("GET", "/healthz")
    async def health(event, bot):
        return "ok"

    @bot.command("ping")
    async def ping(ctx):
        return await ctx.send("pong")

    # an interaction endpoint URL with a path segment must still reach dispatch
    result = bot.handle(_event("POST", "/discord/interactions", body=json.dumps({"type": 2, "data": {"name": "ping"}})))
    assert json.loads(result["body"])["data"]["content"] == "pong"


def test_handle_unmatched_non_post_is_still_404():
    bot = Cordless()

    @bot.route("POST", "/stripe")
    async def hook(event, bot):
        return "ok"

    result = bot.handle(_event("GET", "/nope"))
    assert result["statusCode"] == 404


def test_handle_route_skips_signature_verification():
    bot = Cordless(public_key="0" * 64)

    @bot.route("POST", "/stripe/webhook")
    async def hook(event, bot):
        return "ok"

    result = bot.handle(_event("POST", "/stripe/webhook", body="{}"))
    assert result["statusCode"] == 200
    assert result["body"] == "ok"


def test_handle_route_cordless_error_is_400():
    bot = Cordless()

    @bot.route("GET", "/boom")
    async def boom(event, bot):
        raise CordlessError("nope")

    result = bot.handle(_event("GET", "/boom"))
    assert result["statusCode"] == 400
    assert json.loads(result["body"])["error"] == "nope"


def test_handle_route_unexpected_error_is_500():
    bot = Cordless()

    @bot.route("GET", "/boom")
    async def boom(event, bot):
        raise RuntimeError("kaboom")

    result = bot.handle(_event("GET", "/boom"))
    assert result["statusCode"] == 500


def test_handle_route_unusable_return_value_is_500_not_unhandled():
    """A handler returning something build_response can't coerce (a bool)
    used to let the ValueError escape handle() as an unhandled 502."""
    bot = Cordless()

    @bot.route("GET", "/health")
    async def health(event, bot):
        return True

    result = bot.handle(_event("GET", "/health"))
    assert result["statusCode"] == 500
    assert "bool" in json.loads(result["body"])["error"]


def test_bot_without_routes_is_untouched():
    bot = Cordless()

    @bot.command("ping")
    async def ping(ctx):
        return await ctx.send("pong")

    result = bot.handle({"body": json.dumps({"type": 2, "data": {"name": "ping"}})})
    assert json.loads(result["body"])["data"]["content"] == "pong"


def test_static_route_beats_parameter_route():
    bot = Cordless()

    @bot.route("GET", "/u/{name}")
    async def dynamic(event, bot):
        return "dynamic"

    @bot.route("GET", "/u/me")
    async def static(event, bot):
        return "static"

    assert bot.handle(_event("GET", "/u/me"))["body"] == "static"
    assert bot.handle(_event("GET", "/u/alice"))["body"] == "dynamic"


# --- Cog ---


def test_cog_route_registers():
    bot = Cordless()
    cog = Cog()

    @cog.route("GET", "/healthz")
    async def health(event, bot):
        return "ok"

    bot.add_cog(cog)
    assert bot.handle(_event("GET", "/healthz"))["body"] == "ok"


# --- testing.invoke_route ---


def test_invoke_route_helper():
    bot = Cordless()

    @bot.route("POST", "/gh/{repo}/hook")
    async def hook(event, bot):
        return {"repo": event["pathParameters"]["repo"], "body": json.loads(event["body"])}

    resp = run(invoke_route(bot, "POST", "/gh/cordless/hook", body='{"ref": "main"}'))
    assert resp.status == 200
    assert resp.body == {"repo": "cordless", "body": {"ref": "main"}}


def test_invoke_route_helper_unmatched():
    bot = Cordless()

    @bot.route("GET", "/healthz")
    async def health(event, bot):
        return "ok"

    resp = run(invoke_route(bot, "GET", "/missing"))
    assert resp.status == 404
