"""Data coordinator for Enable Banking balances."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EnableBankingApi, EnableBankingAuthError, EnableBankingError
from .const import CONF_ASPSP_NAME, CONF_SESSION_ID, DOMAIN, SCAN_INTERVAL

BALANCE_PRIORITY = ("ITAV", "CLAV", "ITBD", "CLBD")
LOGGER = logging.getLogger(__name__)


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


class EnableBankingCoordinator(DataUpdateCoordinator[dict[str, AccountBalance]]):
    """Fetch Enable Banking account balances at a shared interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: EnableBankingApi,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.config_entry = entry
        self.api = api
        self._account_details: dict[str, dict[str, Any]] = {}

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
                details = self._account_details.get(account_id)
                if details is None:
                    details = await self.api.async_get_account_details(account_id)
                    self._account_details[account_id] = details
                selected = select_current_balance(
                    await self.api.async_get_balances(account_id)
                )
                if selected is None:
                    continue
                amount_data = selected["balance_amount"]
                try:
                    amount = Decimal(str(amount_data["amount"]))
                except (InvalidOperation, KeyError, TypeError) as err:
                    raise UpdateFailed(
                        "Bank returned an invalid balance amount"
                    ) from err
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
                result[account_key] = AccountBalance(
                    account_id=account_id,
                    stable_id=account_key,
                    name=str(name),
                    currency=currency,
                    amount=amount,
                    balance_type=selected.get("balance_type"),
                    balance_name=selected.get("name"),
                    last_changed=selected.get("last_change_date_time"),
                )
            return result
        except EnableBankingAuthError as err:
            raise ConfigEntryAuthFailed from err
        except EnableBankingError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def bank_name(self) -> str:
        """Return the configured bank name."""
        return self.config_entry.data[CONF_ASPSP_NAME]
