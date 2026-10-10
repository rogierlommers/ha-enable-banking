"""Balance sensors for Enable Banking."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AccountBalance, EnableBankingCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up account balance sensors."""
    coordinator: EnableBankingCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for account_key in coordinator.data:
        entities.append(EnableBankingBalanceSensor(coordinator, account_key))
        if coordinator.transaction_count:
            entities.append(EnableBankingTransactionsSensor(coordinator, account_key))
    async_add_entities(entities)


class EnableBankingBalanceSensor(
    CoordinatorEntity[EnableBankingCoordinator], SensorEntity
):
    """Represent the current balance of one bank account."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_has_entity_name = True
    _attr_translation_key = "balance"

    def __init__(
        self,
        coordinator: EnableBankingCoordinator,
        account_key: str,
    ) -> None:
        """Initialize a balance sensor."""
        super().__init__(coordinator)
        self._account_key = account_key
        account = coordinator.data[account_key]
        self._attr_unique_id = f"{account.stable_id}_balance"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account.stable_id)},
            name=account.name,
            manufacturer=coordinator.bank_name,
            model="Bank account",
        )

    @property
    def _account(self) -> AccountBalance | None:
        return self.coordinator.data.get(self._account_key)

    @property
    def available(self) -> bool:
        """Return whether account balance data is available."""
        return super().available and self._account is not None

    @property
    def native_value(self) -> Decimal | None:
        """Return the current balance."""
        return self._account.amount if self._account else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the account currency."""
        return self._account.currency if self._account else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return non-sensitive balance metadata."""
        if (account := self._account) is None:
            return {}
        return {
            "balance_type": account.balance_type,
            "balance_name": account.balance_name,
            "last_changed": account.last_changed,
        }


class EnableBankingTransactionsSensor(
    CoordinatorEntity[EnableBankingCoordinator], SensorEntity
):
    """Represent recent transactions for one bank account."""

    _attr_has_entity_name = True
    _attr_translation_key = "recent_transactions"
    _attr_icon = "mdi:bank-transfer"

    def __init__(
        self,
        coordinator: EnableBankingCoordinator,
        account_key: str,
    ) -> None:
        """Initialize a recent-transactions sensor."""
        super().__init__(coordinator)
        self._account_key = account_key
        account = coordinator.data[account_key]
        self._attr_unique_id = f"{account.stable_id}_recent_transactions"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account.stable_id)},
            name=account.name,
            manufacturer=coordinator.bank_name,
            model="Bank account",
        )

    @property
    def _account(self) -> AccountBalance | None:
        return self.coordinator.data.get(self._account_key)

    @property
    def available(self) -> bool:
        """Return whether recent transaction data is available."""
        return (
            super().available
            and self._account is not None
            and self._account.transactions is not None
        )

    @property
    def native_value(self) -> int | None:
        """Return the number of recent transactions exposed."""
        if self._account is None or self._account.transactions is None:
            return None
        return len(self._account.transactions)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return capped privacy-conscious transaction summaries."""
        if (account := self._account) is None or account.transactions is None:
            return {}
        return {
            "transactions": [item.as_dict() for item in account.transactions],
            "configured_limit": self.coordinator.transaction_count,
        }
