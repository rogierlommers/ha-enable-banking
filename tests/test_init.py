"""Integration lifecycle tests for Enable Banking."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enable_banking.const import (
    CONF_APPLICATION_ID,
    CONF_ASPSP_NAME,
    CONF_CONSENT_DAYS,
    CONF_COUNTRY,
    CONF_PRIVATE_KEY,
    CONF_PSU_TYPE,
    CONF_SESSION_ID,
    CONF_TRANSACTION_COUNT,
    CONF_TRANSACTION_LOOKBACK_DAYS,
    DOMAIN,
)
from custom_components.enable_banking.coordinator import stable_account_id


async def test_entry_setup_options_reload_and_unload(hass: HomeAssistant) -> None:
    """The real config-entry lifecycle creates, reloads, and removes entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="application-id:NL:Example Bank:personal",
        data={
            CONF_APPLICATION_ID: "application-id",
            CONF_PRIVATE_KEY: "private-key",
            CONF_COUNTRY: "NL",
            CONF_ASPSP_NAME: "Example Bank",
            CONF_PSU_TYPE: "personal",
            CONF_CONSENT_DAYS: 90,
            CONF_SESSION_ID: "session-id",
        },
        options={CONF_TRANSACTION_COUNT: 0},
    )
    entry.add_to_hass(hass)
    account_hash = "provider-account-hash"
    stable_id = stable_account_id(account_hash)

    with (
        patch(
            "custom_components.enable_banking.aiohttp_client.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.enable_banking.api.EnableBankingApi.async_get_session",
            new=AsyncMock(
                return_value={"status": "AUTHORIZED", "accounts": ["account-id"]}
            ),
        ),
        patch(
            "custom_components.enable_banking.api.EnableBankingApi."
            "async_get_account_details",
            new=AsyncMock(
                return_value={
                    "identification_hash": account_hash,
                    "name": "Current account",
                    "currency": "EUR",
                }
            ),
        ),
        patch(
            "custom_components.enable_banking.api.EnableBankingApi.async_get_balances",
            new=AsyncMock(
                return_value=[
                    {
                        "balance_type": "ITAV",
                        "balance_amount": {
                            "amount": "123.45",
                            "currency": "EUR",
                        },
                    }
                ]
            ),
        ),
        patch(
            "custom_components.enable_banking.api.EnableBankingApi."
            "async_get_transactions",
            new=AsyncMock(
                return_value=[
                    {
                        "booking_date": "2026-10-10",
                        "transaction_amount": {
                            "amount": "12.34",
                            "currency": "EUR",
                        },
                        "credit_debit_indicator": "DBIT",
                        "status": "BOOK",
                        "creditor": {"name": "Example Shop"},
                    }
                ]
            ),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        balance_entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{stable_id}_balance"
        )
        assert balance_entity_id is not None
        assert hass.states.get(balance_entity_id).state == "123.45"
        assert (
            registry.async_get_entity_id(
                "sensor", DOMAIN, f"{stable_id}_recent_transactions"
            )
            is None
        )

        hass.config_entries.async_update_entry(
            entry,
            options={
                CONF_TRANSACTION_COUNT: 1,
                CONF_TRANSACTION_LOOKBACK_DAYS: 30,
            },
        )
        await hass.async_block_till_done()

        transaction_entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{stable_id}_recent_transactions"
        )
        assert transaction_entity_id is not None
        assert hass.states.get(transaction_entity_id).state == "1"

        assert await hass.config_entries.async_unload(entry.entry_id)
        balance_state = hass.states.get(balance_entity_id)
        transaction_state = hass.states.get(transaction_entity_id)
        assert balance_state is None or balance_state.attributes.get("restored") is True
        assert (
            transaction_state is None
            or transaction_state.attributes.get("restored") is True
        )
        assert entry.entry_id not in hass.data[DOMAIN]
