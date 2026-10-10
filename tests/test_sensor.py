"""Tests for Enable Banking balance sensors."""

from decimal import Decimal
from unittest.mock import MagicMock

from custom_components.enable_banking.coordinator import AccountBalance
from custom_components.enable_banking.sensor import EnableBankingBalanceSensor


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
        )
    }

    sensor = EnableBankingBalanceSensor(coordinator, "stable-hash")

    assert sensor.native_value == Decimal("123.45")
    assert sensor.native_unit_of_measurement == "EUR"
    assert "secret-account-id" not in str(sensor.extra_state_attributes)
