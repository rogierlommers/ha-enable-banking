"""Tests for balance selection."""

from custom_components.enable_banking.coordinator import (
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
