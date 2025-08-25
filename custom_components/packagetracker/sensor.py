from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN,
    SIGNAL_NEW_PACKAGE,
    SIGNAL_REMOVED_PACKAGE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up sensors from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    # Create initial sensors
    packages_data = await data["store"].async_load() or {}
    packages = packages_data.get("packages", [])

    entities: list[SensorEntity] = []

    for pkg in packages:
        entities.append(PackageDetailedSensor(coordinator, pkg))
        entities.append(PackageShortSensor(coordinator, pkg))

    # Aggregate sensor
    entities.append(PackagesTodayAggregateSensor(coordinator))

    async_add_entities(entities)

    # Listen for new packages to dynamically add sensors
    async def _handle_new(pkg):
        _LOGGER.debug("Adding sensors for new package %s", pkg)
        async_add_entities([PackageDetailedSensor(coordinator, pkg), PackageShortSensor(coordinator, pkg)])

    hass.bus.async_listen(SIGNAL_NEW_PACKAGE, lambda event: _handle_new(event.data.get("package")))



class BasePackageSensor(SensorEntity):
    _attr_should_poll = False

    def __init__(self, coordinator, pkg: dict[str, Any]) -> None:
        self.coordinator = coordinator
        self.pkg = pkg  # dict with id, provider, tracking_number, name
        self._attr_unique_id = f"{self.pkg['id']}-{self.kind}"
        self._attr_name = f"{self.pkg.get('name') or self.pkg['tracking_number']} ({self.pkg['provider'].upper()}) - {self.kind_title}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.pkg["id"])},
            name=self.pkg.get("name") or self.pkg["tracking_number"],
            manufacturer="Package Tracker",
            model=self.pkg["provider"].upper(),
        )

    @property
    def available(self) -> bool:
        data = self.coordinator.data.get(self.pkg["id"])
        return data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.coordinator.data.get(self.pkg["id"], {})
        out = {
            "provider": self.pkg.get("provider"),
            "tracking_number": self.pkg.get("tracking_number"),
            "friendly_name": data.get("friendly_name"),
            "last_update": data.get("last_update"),
        }
        raw = data.get("raw")
        if raw is not None:
            out["raw"] = raw
        return out

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    @property
    def kind(self) -> str:
        raise NotImplementedError

    @property
    def kind_title(self) -> str:
        raise NotImplementedError


class PackageDetailedSensor(BasePackageSensor):
    @property
    def kind(self) -> str:
        return "detailed"

    @property
    def kind_title(self) -> str:
        return "Detailed Status"

    @property
    def native_value(self):
        data = self.coordinator.data.get(self.pkg["id"], {})
        return data.get("detailed_status") or data.get("error") or "Unknown"


class PackageShortSensor(BasePackageSensor):
    @property
    def kind(self) -> str:
        return "short"

    @property
    def kind_title(self) -> str:
        return "Short Status"

    @property
    def native_value(self):
        data = self.coordinator.data.get(self.pkg["id"], {})
        return data.get("short_status") or "In transit"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.coordinator.data.get(self.pkg["id"], {})
        base = super().extra_state_attributes or {}
        base["out_for_delivery_today"] = data.get("out_for_delivery_today", False)
        return base


class PackagesTodayAggregateSensor(SensorEntity):
    _attr_should_poll = False

    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = "packages_today_aggregate"
        self._attr_name = "Packages Delivering Today"

    @property
    def available(self) -> bool:
        return "_aggregate_today" in self.coordinator.data

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self):
        agg = self.coordinator.data.get("_aggregate_today", {})
        return agg.get("state", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        agg = self.coordinator.data.get("_aggregate_today", {})
        return {
            "courier_today": agg.get("courier_today", 0),
            "parcel_locker_today": agg.get("parcel_locker_today", 0),
            "as_of": agg.get("as_of"),
        }