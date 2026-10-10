"""Data coordinator for Enable Banking balances."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EnableBankingApi, EnableBankingAuthError, EnableBankingError
from .const import (
    CONF_ASPSP_NAME,
    CONF_REFRESH_INTERVAL,
    CONF_SESSION_ID,
    CONF_TRANSACTION_COUNT,
    CONF_TRANSACTION_LOOKBACK_DAYS,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_TRANSACTION_COUNT,
    DEFAULT_TRANSACTION_LOOKBACK_DAYS,
    DOMAIN,
    MAX_REFRESH_INTERVAL,
    MAX_TRANSACTION_COUNT,
    MIN_REFRESH_INTERVAL,
)

BALANCE_PRIORITY = ("ITAV", "CLAV", "ITBD", "CLBD")
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TransactionSummary:
    """Privacy-conscious transaction data exposed to Home Assistant."""

    date: str
    amount: str
    currency: str
    direction: str
    status: str | None
    counterparty: str | None
    remittance: str | None

    def as_dict(self) -> dict[str, str | None]:
        """Return a JSON-serializable state attribute."""
        return {
            "date": self.date,
            "amount": self.amount,
            "currency": self.currency,
            "direction": self.direction,
            "status": self.status,
            "counterparty": self.counterparty,
            "remittance": self.remittance,
        }


@dataclass(frozen=True, slots=True)
class AccountBalance:
    """Normalized current account balance."""

    account_id: str
    stable_id: str
    name: str
    currency: str
    amount: Decimal
    balance_type: str | None
    balance_name: str | None
    last_changed: str | None
    transactions: tuple[TransactionSummary, ...] | None


def select_current_balance(balances: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the best current balance returned by a bank."""
    valid = [
        balance
        for balance in balances
        if isinstance(balance.get("balance_amount"), dict)
        and balance["balance_amount"].get("amount") is not None
    ]
    for balance_type in BALANCE_PRIORITY:
        if match := next(
            (item for item in valid if item.get("balance_type") == balance_type),
            None,
        ):
            return match
    return valid[0] if valid else None


def stable_account_id(provider_identifier: str) -> str:
    """Return a stable opaque identifier without retaining provider account data."""
    return hashlib.sha256(provider_identifier.encode()).hexdigest()


def _clean_text(value: Any, max_length: int) -> str | None:
    """Normalize API text and cap recorder payload growth."""
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:max_length] or None


def normalize_transaction(transaction: dict[str, Any]) -> TransactionSummary | None:
    """Create a safe transaction summary without banking identifiers."""
    amount_data = transaction.get("transaction_amount")
    if not isinstance(amount_data, dict):
        return None
    amount_value = amount_data.get("amount")
    currency_value = amount_data.get("currency")
    try:
        amount = Decimal(str(amount_value))
    except (InvalidOperation, TypeError):
        return None
    if (
        not amount.is_finite()
        or not isinstance(currency_value, str)
        or len(currency_value) != 3
        or not currency_value.isalpha()
    ):
        return None

    date = next(
        (
            value
            for key in ("booking_date", "transaction_date", "value_date")
            if isinstance((value := transaction.get(key)), str) and value
        ),
        None,
    )
    if date is None:
        return None

    indicator = transaction.get("credit_debit_indicator")
    direction = {"CRDT": "credit", "DBIT": "debit"}.get(indicator, "unknown")
    counterparty_key = "debtor" if direction == "credit" else "creditor"
    counterparty_data = transaction.get(counterparty_key)
    counterparty = (
        _clean_text(counterparty_data.get("name"), 128)
        if isinstance(counterparty_data, dict)
        else None
    )

    remittance_data = transaction.get("remittance_information")
    if isinstance(remittance_data, list):
        remittance = _clean_text(
            " | ".join(item for item in remittance_data if isinstance(item, str)),
            256,
        )
    else:
        remittance = _clean_text(remittance_data, 256)

    return TransactionSummary(
        date=date[:32],
        amount=format(amount, "f"),
        currency=currency_value.upper(),
        direction=direction,
        status=_clean_text(transaction.get("status"), 32),
        counterparty=counterparty,
        remittance=remittance,
    )


class EnableBankingCoordinator(DataUpdateCoordinator[dict[str, AccountBalance]]):
    """Fetch Enable Banking account balances at a shared interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: EnableBankingApi,
    ) -> None:
        """Initialize the coordinator."""
        refresh_interval = max(
            MIN_REFRESH_INTERVAL,
            min(
                MAX_REFRESH_INTERVAL,
                int(entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL)),
            ),
        )
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=refresh_interval),
        )
        self.config_entry = entry
        self.api = api
        self.transaction_count = max(
            0,
            min(
                MAX_TRANSACTION_COUNT,
                int(
                    entry.options.get(CONF_TRANSACTION_COUNT, DEFAULT_TRANSACTION_COUNT)
                ),
            ),
        )
        configured_lookback = int(
            entry.options.get(
                CONF_TRANSACTION_LOOKBACK_DAYS,
                DEFAULT_TRANSACTION_LOOKBACK_DAYS,
            )
        )
        self.transaction_lookback_days = (
            configured_lookback
            if configured_lookback in {7, 30, 90, 365}
            else DEFAULT_TRANSACTION_LOOKBACK_DAYS
        )
        self._account_details: dict[str, dict[str, Any]] = {}

    async def _async_get_account_balance(
        self, account_id: str
    ) -> AccountBalance | None:
        """Fetch and normalize one account with its optional transactions."""
        details = self._account_details.get(account_id)
        if details is None:
            details = await self.api.async_get_account_details(account_id)
            self._account_details[account_id] = details
        selected = select_current_balance(await self.api.async_get_balances(account_id))
        if selected is None:
            return None
        amount_data = selected["balance_amount"]
        try:
            amount = Decimal(str(amount_data["amount"]))
        except (InvalidOperation, KeyError, TypeError) as err:
            raise UpdateFailed("Bank returned an invalid balance amount") from err
        if not amount.is_finite():
            raise UpdateFailed("Bank returned a non-finite balance amount")

        identification_hash = details.get("identification_hash")
        if not isinstance(identification_hash, str):
            identification_hash = account_id
        account_key = stable_account_id(identification_hash)
        currency = amount_data.get("currency") or details.get("currency")
        if (
            not isinstance(currency, str)
            or len(currency) != 3
            or not currency.isalpha()
        ):
            raise UpdateFailed("Bank returned an invalid balance currency")
        currency = currency.upper()
        name = details.get("name") or details.get("product") or "Bank account"
        transactions: tuple[TransactionSummary, ...] | None = ()
        if self.transaction_count:
            try:
                summaries = [
                    summary
                    for transaction in await self.api.async_get_transactions(
                        account_id,
                        self.transaction_count,
                        date_from=datetime.now(tz=UTC).date()
                        - timedelta(days=self.transaction_lookback_days),
                    )
                    if (summary := normalize_transaction(transaction)) is not None
                ]
            except EnableBankingAuthError:
                raise
            except EnableBankingError as err:
                LOGGER.warning(
                    "Unable to update recent transactions for account %s: %s",
                    account_key,
                    err,
                )
                transactions = None
            else:
                transactions = tuple(
                    sorted(summaries, key=lambda item: item.date, reverse=True)[
                        : self.transaction_count
                    ]
                )
        return AccountBalance(
            account_id=account_id,
            stable_id=account_key,
            name=str(name),
            currency=currency,
            amount=amount,
            balance_type=selected.get("balance_type"),
            balance_name=selected.get("name"),
            last_changed=selected.get("last_change_date_time"),
            transactions=transactions,
        )

    async def _async_update_data(self) -> dict[str, AccountBalance]:
        try:
            session = await self.api.async_get_session(
                self.config_entry.data[CONF_SESSION_ID]
            )
            if session.get("status") != "AUTHORIZED":
                raise ConfigEntryAuthFailed("Bank authorization must be renewed")

            account_ids = session.get("accounts", [])
            if not isinstance(account_ids, list):
                raise UpdateFailed("Enable Banking returned invalid session data")

            result: dict[str, AccountBalance] = {}
            for account_id in account_ids:
                if not isinstance(account_id, str):
                    continue
                if account := await self._async_get_account_balance(account_id):
                    result[account.stable_id] = account
            return result
        except EnableBankingAuthError as err:
            raise ConfigEntryAuthFailed from err
        except EnableBankingError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def bank_name(self) -> str:
        """Return the configured bank name."""
        return self.config_entry.data[CONF_ASPSP_NAME]
