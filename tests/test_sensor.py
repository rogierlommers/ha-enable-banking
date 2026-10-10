"""Tests for Enable Banking balance sensors."""

from decimal import Decimal
from unittest.mock import MagicMock

from custom_components.enable_banking.coordinator import (
    AccountBalance,
    TransactionSummary,
)
from custom_components.enable_banking.sensor import (
    EnableBankingBalanceSensor,
    EnableBankingTransactionsSensor,
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
