"""Balance sensors for Enable Banking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import ceil
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AccountBalance, EnableBankingCoordinator


def authentication_days_remaining(valid_until: datetime, now: datetime) -> int:
    """Return whole days remaining, rounding a partial final day up."""
    return max(0, ceil((valid_until - now) / timedelta(days=1)))


def next_authentication_expiry_update(
    valid_until: datetime, now: datetime
) -> datetime | None:
    """Return when the rounded days-remaining state next changes."""
    days_remaining = authentication_days_remaining(valid_until, now)
    if days_remaining == 0:
        return None
    return valid_until - timedelta(days=days_remaining - 1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up account balance sensors."""
    coordinator: EnableBankingCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_accounts: set[str] = set()

    async_add_entities(
        [
            EnableBankingLastRefreshSensor(coordinator, entry),
            EnableBankingAuthenticationExpirySensor(coordinator, entry),
        ]
    )

    @callback
    def async_add_missing_entities() -> None:
        """Add entities for accounts first observed after platform setup."""
        entities: list[SensorEntity] = []
        for account_key in coordinator.data.keys() - known_accounts:
            known_accounts.add(account_key)
            entities.append(EnableBankingBalanceSensor(coordinator, account_key))
            if coordinator.transaction_count:
                entities.append(
                    EnableBankingTransactionsSensor(coordinator, account_key)
                )
        if entities:
            async_add_entities(entities)

    async_add_missing_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_missing_entities))


class EnableBankingLastRefreshSensor(
    CoordinatorEntity[EnableBankingCoordinator], SensorEntity
):
    """Represent the time of the most recent successful data refresh."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True
    _attr_translation_key = "last_refresh"

    def __init__(
        self,
        coordinator: EnableBankingCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the last-refresh sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_refresh"

    @property
    def native_value(self) -> datetime | None:
        """Return the most recent successful refresh time."""
        return self.coordinator.last_refresh

    @property
    def available(self) -> bool:
        """Keep the last successful refresh visible after update failures."""
        return self.coordinator.last_refresh is not None


class EnableBankingAuthenticationExpirySensor(
    CoordinatorEntity[EnableBankingCoordinator], SensorEntity
):
    """Represent the number of days until bank authentication expires."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "authentication_expires_in"

    def __init__(
        self,
        coordinator: EnableBankingCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the authentication-expiry sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_authentication_expires_in"
        self._cancel_expiry_update: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Schedule updates at rounded day boundaries."""
        await super().async_added_to_hass()
        self._schedule_expiry_update()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the scheduled boundary update."""
        if self._cancel_expiry_update is not None:
            self._cancel_expiry_update()
            self._cancel_expiry_update = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Reschedule when the provider reports a new expiry."""
        self._schedule_expiry_update()
        super()._handle_coordinator_update()

    @callback
    def _schedule_expiry_update(self) -> None:
        """Schedule the next day-boundary or exact-expiry update."""
        if self._cancel_expiry_update is not None:
            self._cancel_expiry_update()
            self._cancel_expiry_update = None
        if self.coordinator.session_valid_until is None:
            return
        update_at = next_authentication_expiry_update(
            self.coordinator.session_valid_until, datetime.now(tz=UTC)
        )
        if update_at is not None:
            self._cancel_expiry_update = async_track_point_in_utc_time(
                self.hass, self._async_expiry_update, update_at
            )

    @callback
    def _async_expiry_update(self, _now: datetime) -> None:
        """Publish the new rounded value and schedule the next boundary."""
        self._cancel_expiry_update = None
        self.async_write_ha_state()
        self._schedule_expiry_update()

    @property
    def native_value(self) -> int | None:
        """Return whole days remaining, rounding a partial final day up."""
        if self.coordinator.session_valid_until is None:
            return None
        return authentication_days_remaining(
            self.coordinator.session_valid_until, datetime.now(tz=UTC)
        )

    @property
    def available(self) -> bool:
        """Keep the last known expiry visible after transient update failures."""
        return self.coordinator.session_valid_until is not None


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
