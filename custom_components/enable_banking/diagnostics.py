"""Diagnostics for Enable Banking."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PRIVATE_KEY, CONF_SESSION_ID, DOMAIN
from .coordinator import EnableBankingCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics with credentials and banking identifiers removed."""
    coordinator: EnableBankingCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = {
        key: value
        for key, value in entry.data.items()
        if key not in {CONF_PRIVATE_KEY, CONF_SESSION_ID}
    }
    return {
        "config_entry": data,
        "last_update_success": coordinator.last_update_success,
        "account_count": len(coordinator.data),
        "currencies": sorted(
            {account.currency for account in coordinator.data.values()}
        ),
    }
