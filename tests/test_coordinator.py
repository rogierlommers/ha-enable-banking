"""Tests for balance selection."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enable_banking.api import EnableBankingError
from custom_components.enable_banking.const import (
    CONF_ASPSP_NAME,
    CONF_REFRESH_INTERVAL,
    CONF_SESSION_ID,
    CONF_TRANSACTION_COUNT,
    DOMAIN,
)
from custom_components.enable_banking.coordinator import (
    EnableBankingCoordinator,
    normalize_transaction,
    select_current_balance,
    stable_account_id,
)


def _balance(balance_type: str, amount: str) -> dict:
    return {
        "balance_type": balance_type,
        "balance_amount": {"amount": amount, "currency": "EUR"},
    }


def test_selects_interim_available_balance() -> None:
    """The most current available balance wins regardless of API order."""
    selected = select_current_balance([_balance("CLBD", "10"), _balance("ITAV", "8")])
    assert selected is not None
    assert selected["balance_type"] == "ITAV"


def test_falls_back_to_first_valid_balance() -> None:
    """Unknown bank-specific balance types remain usable."""
    selected = select_current_balance([{"name": "invalid"}, _balance("BANK", "12")])
    assert selected is not None
    assert selected["balance_type"] == "BANK"


def test_returns_none_without_balance_amount() -> None:
    """Malformed responses do not produce a sensor state."""
    assert select_current_balance([{"balance_type": "ITAV"}]) is None


def test_account_identifier_is_stable_and_opaque() -> None:
    """Provider account identifiers are never used directly in entity IDs."""
    provider_identifier = "identification-hash-containing-account-data"
    result = stable_account_id(provider_identifier)

    assert result == stable_account_id(provider_identifier)
    assert provider_identifier not in result
    assert len(result) == 64


def test_transaction_summary_omits_sensitive_account_data() -> None:
    """Transaction summaries expose useful fields without account identifiers."""
    summary = normalize_transaction(
        {
            "booking_date": "2026-10-10",
            "transaction_amount": {"amount": "12.34", "currency": "EUR"},
            "credit_debit_indicator": "DBIT",
            "status": "BOOK",
            "creditor": {"name": "Example Shop"},
            "creditor_account": {"iban": "NL00SECRET0123456789"},
            "remittance_information": ["Order 123", "Thank you"],
            "transaction_id": "provider-secret-id",
        }
    )

    assert summary is not None
    attributes = summary.as_dict()
    assert attributes == {
        "date": "2026-10-10",
        "amount": "12.34",
        "currency": "EUR",
        "direction": "debit",
        "status": "BOOK",
        "counterparty": "Example Shop",
        "remittance": "Order 123 | Thank you",
    }
    assert "NL00SECRET" not in str(attributes)
    assert "provider-secret-id" not in str(attributes)


def test_coordinator_uses_refresh_and_transaction_options(
    hass: HomeAssistant,
) -> None:
    """Coordinator bounds and applies user-configured polling behavior."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_REFRESH_INTERVAL: 30, CONF_TRANSACTION_COUNT: 5},
    )
    entry.add_to_hass(hass)

    coordinator = EnableBankingCoordinator(hass, entry, MagicMock())

    assert coordinator.update_interval == timedelta(minutes=30)
    assert coordinator.transaction_count == 5


async def test_transaction_failure_keeps_balance_update_available(
    hass: HomeAssistant,
) -> None:
    """An optional transaction failure does not make balance data unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SESSION_ID: "session-id", CONF_ASPSP_NAME: "Example Bank"},
        options={CONF_TRANSACTION_COUNT: 5},
    )
    entry.add_to_hass(hass)
    api = MagicMock()
    api.async_get_session = AsyncMock(
        return_value={"status": "AUTHORIZED", "accounts": ["account-id"]}
    )
    api.async_get_account_details = AsyncMock(
        return_value={
            "identification_hash": "provider-account-hash",
            "name": "Current account",
            "currency": "EUR",
        }
    )
    api.async_get_balances = AsyncMock(
        return_value=[
            {
                "balance_type": "ITAV",
                "balance_amount": {"amount": "123.45", "currency": "EUR"},
            }
        ]
    )
    api.async_get_transactions = AsyncMock(
        side_effect=EnableBankingError("Transactions unavailable")
    )
    coordinator = EnableBankingCoordinator(hass, entry, api)

    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    account = next(iter(coordinator.data.values()))
    assert account.amount.is_finite()
    assert account.transactions is None
