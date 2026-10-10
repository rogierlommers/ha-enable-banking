"""Enable Banking integration setup."""

from __future__ import annotations

from typing import Any

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import config_validation as cv

from .api import EnableBankingApi
from .const import (
    CALLBACK_PATH,
    CONF_APPLICATION_ID,
    CONF_PRIVATE_KEY,
    DATA_CALLBACK_REGISTERED,
    DATA_PENDING_FLOWS,
    DOMAIN,
)
from .coordinator import EnableBankingCoordinator

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class EnableBankingCallbackView(HomeAssistantView):
    """Receive Enable Banking authorization callbacks."""

    url = CALLBACK_PATH
    name = "api:enable_banking:callback"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Pass a one-time callback to its active config flow."""
        hass: HomeAssistant = request.app[KEY_HASS]
        state = request.query.get("state", "")
        pending: dict[str, str] = hass.data[DOMAIN][DATA_PENDING_FLOWS]
        flow_id = pending.pop(state, None)
        if flow_id is None:
            return web.Response(
                text="Invalid or expired authorization request",
                status=400,
                headers={
                    "Cache-Control": "no-store",
                    "Referrer-Policy": "no-referrer",
                },
            )

        user_input = {
            key: request.query[key]
            for key in ("code", "state", "error", "error_description")
            if key in request.query
        }
        try:
            await hass.config_entries.flow.async_configure(
                flow_id, user_input=user_input
            )
        except UnknownFlow:
            return web.Response(text="Authorization request expired", status=400)

        return web.Response(
            text=(
                "Enable Banking authorization received. "
                "Return to Home Assistant to finish setup."
            ),
            content_type="text/plain",
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
            },
        )


@callback
def async_ensure_callback_registered(hass: HomeAssistant) -> None:
    """Register callback handling once, including during a config flow."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data.setdefault(DATA_PENDING_FLOWS, {})
    if domain_data.get(DATA_CALLBACK_REGISTERED):
        return
    hass.http.register_view(EnableBankingCallbackView)
    domain_data[DATA_CALLBACK_REGISTERED] = True


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Initialize callback handling for config flows."""
    async_ensure_callback_registered(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enable Banking from a config entry."""
    api = EnableBankingApi(
        aiohttp_client.async_get_clientsession(hass),
        entry.data[CONF_APPLICATION_ID],
        entry.data[CONF_PRIVATE_KEY],
    )
    coordinator = EnableBankingCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Enable Banking config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
