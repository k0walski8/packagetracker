from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers.storage import Store

from .const import DOMAIN, PLATFORMS, STORAGE_VERSION
from .coordinator import PackageUpdateCoordinator
from .http import async_register_http_panel_and_routes

_LOGGER = logging.getLogger(__name__)

# Removed 3.12-only type alias for HA compatibility

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_data")
    existing = await store.async_load() or {}
    # Initialize storage schema
    packages = existing.get("packages", [])
    existing["packages"] = packages
    await store.async_save(existing)

    coordinator = PackageUpdateCoordinator(hass, store)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "store": store,
        "entry": entry,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register Web UI (panel) + REST endpoints to add/remove packages
    await async_register_http_panel_and_routes(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok