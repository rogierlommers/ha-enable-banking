"""Tests for Enable Banking balance sensors."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enable_banking.const import DOMAIN
from custom_components.enable_banking.coordinator import (
    AccountBalance,
    TransactionSummary,
)
from custom_components.enable_banking.sensor import (
    EnableBankingBalanceSensor,
    EnableBankingLastRefreshSensor,
    EnableBankingTransactionsSensor,
    async_setup_entry,
)


def test_sensor_exposes_balance_without_account_identifiers() -> None:
    """The sensor includes useful metadata but no banking identifiers."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.bank_name = "Example Bank"
    coordinator.data = {
        "stable-hash": AccountBalance(
            account_id="secret-account-id",
            stable_id="stable-hash",
            name="Current account",
            currency="EUR",
            amount=Decimal("123.45"),
            balance_type="ITAV",
            balance_name="Available",
            last_changed="2026-10-10T10:00:00Z",
            transactions=(
                TransactionSummary(
                    date="2026-10-09",
                    amount="10.00",
                    currency="EUR",
                    direction="debit",
                    status="BOOK",
                    counterparty="Example Shop",
                    remittance="Order 123",
                ),
            ),
        )
    }
    coordinator.transaction_count = 1

    sensor = EnableBankingBalanceSensor(coordinator, "stable-hash")

    assert sensor.native_value == Decimal("123.45")
    assert sensor.native_unit_of_measurement == "EUR"
    assert "secret-account-id" not in str(sensor.extra_state_attributes)


def test_transactions_sensor_exposes_safe_summaries() -> None:
    """The transactions sensor reports the count and normalized summaries."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.bank_name = "Example Bank"
    coordinator.transaction_count = 1
    coordinator.data = {
        "stable-hash": AccountBalance(
            account_id="secret-account-id",
            stable_id="stable-hash",
            name="Current account",
            currency="EUR",
            amount=Decimal("123.45"),
            balance_type="ITAV",
            balance_name="Available",
            last_changed="2026-10-10T10:00:00Z",
            transactions=(
                TransactionSummary(
                    date="2026-10-09",
                    amount="10.00",
                    currency="EUR",
                    direction="debit",
                    status="BOOK",
                    counterparty="Example Shop",
                    remittance="Order 123",
                ),
            ),
        )
    }

    sensor = EnableBankingTransactionsSensor(coordinator, "stable-hash")

    assert sensor.native_value == 1
    assert sensor.extra_state_attributes == {
        "transactions": [
            {
                "date": "2026-10-09",
                "amount": "10.00",
                "currency": "EUR",
                "direction": "debit",
                "status": "BOOK",
                "counterparty": "Example Shop",
                "remittance": "Order 123",
            }
        ],
        "configured_limit": 1,
    }


def test_transactions_sensor_is_unavailable_after_transaction_fetch_failure() -> None:
    """A transaction API failure does not expose stale or partial attributes."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.bank_name = "Example Bank"
    coordinator.transaction_count = 1
    coordinator.data = {
        "stable-hash": AccountBalance(
            account_id="secret-account-id",
            stable_id="stable-hash",
            name="Current account",
            currency="EUR",
            amount=Decimal("123.45"),
            balance_type="ITAV",
            balance_name="Available",
            last_changed="2026-10-10T10:00:00Z",
            transactions=None,
        )
    }

    sensor = EnableBankingTransactionsSensor(coordinator, "stable-hash")

    assert sensor.available is False
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_last_refresh_sensor_exposes_coordinator_timestamp() -> None:
    """The last-refresh sensor exposes an aware timestamp."""
    refreshed_at = datetime(2026, 10, 17, 12, 30, tzinfo=UTC)
    coordinator = MagicMock()
    coordinator.last_update_success = False
    coordinator.last_refresh = refreshed_at
    entry = MockConfigEntry(domain=DOMAIN)

    sensor = EnableBankingLastRefreshSensor(coordinator, entry)

    assert sensor.native_value == refreshed_at
    assert sensor.available is True
    assert sensor.device_class == "timestamp"


async def test_platform_adds_accounts_seen_after_initial_setup(
    hass: HomeAssistant,
) -> None:
    """Coordinator updates create entities for newly discovered accounts."""
    first = AccountBalance(
        account_id="account-one",
        stable_id="stable-one",
        name="First account",
        currency="EUR",
        amount=Decimal("1.00"),
        balance_type="ITAV",
        balance_name="Available",
        last_changed=None,
        transactions=(),
    )
    second = AccountBalance(
        account_id="account-two",
        stable_id="stable-two",
        name="Second account",
        currency="EUR",
        amount=Decimal("2.00"),
        balance_type="ITAV",
        balance_name="Available",
        last_changed=None,
        transactions=(),
    )
    coordinator = MagicMock()
    coordinator.data = {first.stable_id: first}
    coordinator.transaction_count = 0
    coordinator.bank_name = "Example Bank"
    listeners = []
    coordinator.async_add_listener.side_effect = lambda listener: (
        listeners.append(listener) or MagicMock()
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    added = []

    await async_setup_entry(hass, entry, added.extend)
    assert [entity.unique_id for entity in added] == [
        f"{entry.entry_id}_last_refresh",
        "stable-one_balance",
    ]

    coordinator.data[second.stable_id] = second
    listeners[0]()

    assert [entity.unique_id for entity in added] == [
        f"{entry.entry_id}_last_refresh",
        "stable-one_balance",
        "stable-two_balance",
    ]
