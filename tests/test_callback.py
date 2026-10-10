"""Tests for the public Enable Banking authorization callback."""

import sys
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientResponse
from aiohttp.test_utils import TestClient
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.setup import async_setup_component

from custom_components.enable_banking import async_ensure_callback_registered
from custom_components.enable_banking.const import (
    CALLBACK_PATH,
    DATA_PENDING_FLOWS,
    DOMAIN,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "darwin",
    reason="aiohttp's macOS resolver leaves a pycares shutdown thread behind",
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
    client = await hass_client()
    hass.data[DOMAIN][DATA_PENDING_FLOWS]["valid-state"] = "flow-id"
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
    client = await hass_client()
    hass.data[DOMAIN][DATA_PENDING_FLOWS]["expired-state"] = "expired-flow"

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
