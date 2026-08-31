"""Application REST endpoints (Discord API v10).

fetch_current_application/edit_current_application are keyed on @me: Discord
resolves that to whichever application owns the bot token making the request,
so unlike almost every other resource here there is no id parameter to pass
in.
"""

from . import _client
from ._client import UNSET
from .models import Application, ApplicationRoleConnectionMetadata


async def fetch_current_application(*, token=None):
    """The bot's own `Application`, the object behind its developer-portal listing."""
    data = await _client.request("GET", "/applications/@me", token=token)
    return Application(data)


async def fetch_application_role_connection_metadata(application_id, *, token=None):
    """The Linked Roles metadata records, or `[]` if none are registered."""
    data = await _client.request("GET", f"/applications/{application_id}/role-connections/metadata", token=token)
    return [ApplicationRoleConnectionMetadata(r) for r in data or []]


async def edit_application_role_connection_metadata(application_id, records, *, token=None):
    """records is the full list of up to 5 metadata records - this replaces
    the whole set, same as bulk_overwrite_global_commands does for commands."""
    data = await _client.request(
        "PUT", f"/applications/{application_id}/role-connections/metadata", records, token=token
    )
    return [ApplicationRoleConnectionMetadata(r) for r in data or []]


async def edit_current_application(
    *,
    custom_install_url=UNSET,
    description=UNSET,
    role_connections_verification_url=UNSET,
    install_params=UNSET,
    integration_types_config=UNSET,
    flags=UNSET,
    icon=UNSET,
    cover_image=UNSET,
    interactions_endpoint_url=UNSET,
    tags=UNSET,
    event_webhooks_url=UNSET,
    event_webhooks_status=UNSET,
    event_webhooks_types=UNSET,
    token=None,
):
    """Only a handful of application flags can actually be set this way
    (the GATEWAY_*_LIMITED intents and EMBEDDED) - Discord silently ignores
    the rest."""
    payload = _client.payload(
        custom_install_url=custom_install_url,
        description=description,
        role_connections_verification_url=role_connections_verification_url,
        install_params=install_params,
        integration_types_config=integration_types_config,
        flags=flags,
        icon=icon,
        cover_image=cover_image,
        interactions_endpoint_url=interactions_endpoint_url,
        tags=tags,
        event_webhooks_url=event_webhooks_url,
        event_webhooks_status=event_webhooks_status,
        event_webhooks_types=event_webhooks_types,
    )
    data = await _client.request("PATCH", "/applications/@me", payload, token=token)
    return Application(data)
