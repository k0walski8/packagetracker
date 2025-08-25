
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_add_entities
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_PACKAGES, CARRIER_DHL, CARRIER_INPOST

from .coordinator import PackageDataCoordinator

ATTR_CARRIER = "carrier"
ATTR_NUMBER = "tracking_number"
ATTR_LAST_UPDATE = "last_update"
ATTR_DETAIL = "detail"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = PackageDataCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entities = []
    for pkg in coordinator.packages:
        entities.append(PackageDetailSensor(coordinator, entry, pkg))
        entities.append(PackageShortSensor(coordinator, entry, pkg))

    entities.append(PackagesTodayAggregateSensor(coordinator, entry))

    async_add_entities(entities, True)

class BasePackageSensor(CoordinatorEntity[PackageDataCoordinator], SensorEntity):
    def __init__(self, coordinator: PackageDataCoordinator, entry: ConfigEntry, pkg: dict | None = None) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._pkg = pkg

    @property
    def device_info(self) -> DeviceInfo | None:
        if not self._pkg:
            return DeviceInfo(
                identifiers={(DOMAIN, self._entry.entry_id, "aggregate")},
                name="Polish Package Tracker",
                manufacturer="Community",
                model="Aggregate"
            )
        num = self._pkg["number"]
        name = self._pkg.get("name") or num
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id, num)},
            name=f"Package {name}",
            manufacturer=self._pkg["carrier"].upper(),
            model="Tracking"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self._pkg:
            return {}
        num = self._pkg["number"]
        data = self.coordinator.data.get(num) or {}
        return {
            ATTR_CARRIER: self._pkg["carrier"],
            ATTR_NUMBER: num,
            ATTR_LAST_UPDATE: data.get("last_update"),
            ATTR_DETAIL: data.get("detail"),
        }

class PackageDetailSensor(BasePackageSensor):
    _attr_icon = "mdi:package-variant-closed"

    @property
    def name(self) -> str:
        name = self._pkg.get("name") or self._pkg["number"]
        return f"{name} – detailed status"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._pkg['carrier']}_{self._pkg['number']}_detail"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data.get(self._pkg["number"]) or {}
        return data.get("detail")

class PackageShortSensor(BasePackageSensor):
    _attr_icon = "mdi:package-variant"

    @property
    def name(self) -> str:
        name = self._pkg.get("name") or self._pkg["number"]
        return f"{name} – status"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._pkg['carrier']}_{self._pkg['number']}_short"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data.get(self._pkg["number"]) or {}
        return data.get("short")

class PackagesTodayAggregateSensor(BasePackageSensor):
    _attr_icon = "mdi:calendar-today"
    def __init__(self, coordinator: PackageDataCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, None)

    @property
    def name(self) -> str:
        return "Packages arriving today"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_aggregate_today"

    @property
    def native_value(self) -> int | None:
        # Count packages with short status 'In delivery Today'
        count = 0
        for data in (self.coordinator.data or {}).values():
            if data.get("short") == "In delivery Today":
                count += 1
        return count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        courier = 0
        locker = 0
        # Use package definitions to split by carrier
        defs = {p["number"]: p for p in self.coordinator.packages}
        for number, data in (self.coordinator.data or {}).items():
            if data.get("short") != "In delivery Today":
                continue
            carrier = defs.get(number, {}).get("carrier")
            if carrier == CARRIER_DHL:
                courier += 1
            elif carrier == CARRIER_INPOST:
                locker += 1
        return {
            "courier_today": courier,
            "parcel_locker_today": locker,
        }
