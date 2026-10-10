"""Diagnostics tests for Enable Banking."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enable_banking.const import (
    CONF_APPLICATION_ID,
    CONF_ASPSP_NAME,
    CONF_COUNTRY,
    CONF_PRIVATE_KEY,
    CONF_PSU_TYPE,
    CONF_REFRESH_INTERVAL,
    CONF_SESSION_ID,
    DOMAIN,
)
from custom_components.enable_banking.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_omit_banking_and_credential_metadata(
    hass: HomeAssistant,
) -> None:
    """Downloaded diagnostics contain health/options but no banking identity."""
    sensitive_values = {
        CONF_APPLICATION_ID: "secret-application-id",
        CONF_PRIVATE_KEY: "secret-private-key",
        CONF_SESSION_ID: "secret-session-id",
        CONF_ASPSP_NAME: "Secret Bank",
        CONF_COUNTRY: "NL",
        CONF_PSU_TYPE: "personal",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=sensitive_values,
        options={CONF_REFRESH_INTERVAL: 60},
    )
    entry.add_to_hass(hass)
    coordinator = MagicMock(last_update_success=True)
    coordinator.data = {
        "secret-account-id": MagicMock(
            currency="EUR",
            transactions=[{"transaction_id": "secret-transaction-id"}],
        )
    }
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    serialized = str(diagnostics)

    assert diagnostics == {
        "options": {CONF_REFRESH_INTERVAL: 60},
        "last_update_success": True,
    }
    for sensitive_value in (
        *sensitive_values.values(),
        "secret-account-id",
        "secret-transaction-id",
        "EUR",
    ):
        assert sensitive_value not in serialized
