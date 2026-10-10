"""Tests for the public Enable Banking authorization callback."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

from aiohttp import ClientResponse, ThreadedResolver
from aiohttp.test_utils import TestClient
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.setup import async_setup_component

from custom_components.enable_banking import (
    PendingFlow,
    async_ensure_callback_registered,
    async_pop_pending_flow,
    async_register_pending_flow,
)
from custom_components.enable_banking.const import (
    CALLBACK_PATH,
    DATA_PENDING_FLOWS,
    DOMAIN,
)


def _assert_private_response_headers(response: ClientResponse) -> None:
    """Assert callback responses cannot be cached or sent as referrers."""
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"


async def test_callback_forwards_allowlisted_fields_once(
    hass: HomeAssistant,
    hass_client: Callable[..., Awaitable[TestClient]],
) -> None:
    """A valid callback is forwarded once without unexpected query fields."""
    await async_setup_component(hass, "http", {})
    async_ensure_callback_registered(hass)
    # The optional aiodns resolver leaves a pycares shutdown thread behind.
    with patch("aiohttp.connector.DefaultResolver", ThreadedResolver):
        client = await hass_client()
    async_register_pending_flow(hass, "valid-state", "flow-id")
    configure = AsyncMock()

    with patch.object(hass.config_entries.flow, "async_configure", new=configure):
        response = await client.get(
            CALLBACK_PATH,
            params={
                "state": "valid-state",
                "code": "authorization-code",
                "unexpected": "must-not-be-forwarded",
            },
        )

    assert response.status == 200
    _assert_private_response_headers(response)
    configure.assert_awaited_once_with(
        "flow-id",
        user_input={"code": "authorization-code", "state": "valid-state"},
    )

    replay = await client.get(
        CALLBACK_PATH,
        params={"state": "valid-state", "code": "authorization-code"},
    )
    assert replay.status == 400
    _assert_private_response_headers(replay)


async def test_callback_handles_expired_home_assistant_flow(
    hass: HomeAssistant,
    hass_client: Callable[..., Awaitable[TestClient]],
) -> None:
    """A callback for a removed flow returns a private controlled error."""
    await async_setup_component(hass, "http", {})
    async_ensure_callback_registered(hass)
    # Keep the test client inside Home Assistant's strict thread-cleanup contract.
    with patch("aiohttp.connector.DefaultResolver", ThreadedResolver):
        client = await hass_client()
    async_register_pending_flow(hass, "expired-state", "expired-flow")

    with patch.object(
        hass.config_entries.flow,
        "async_configure",
        new=AsyncMock(side_effect=UnknownFlow),
    ):
        response = await client.get(
            CALLBACK_PATH,
            params={"state": "expired-state", "code": "authorization-code"},
        )

    assert response.status == 400
    _assert_private_response_headers(response)
    assert "authorization-code" not in await response.text()


async def test_expired_callback_state_is_pruned(hass: HomeAssistant) -> None:
    """Abandoned authorization states stop being addressable after expiry."""
    await async_setup_component(hass, "http", {})
    async_ensure_callback_registered(hass)
    hass.data[DOMAIN][DATA_PENDING_FLOWS]["expired-state"] = PendingFlow(
        flow_id="expired-flow",
        expires_at=0,
    )

    assert async_pop_pending_flow(hass, "expired-state") is None
    assert "expired-state" not in hass.data[DOMAIN][DATA_PENDING_FLOWS]
