
from __future__ import annotations
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from .const import DOMAIN, CONF_PACKAGES

async def async_setup_services(hass: HomeAssistant):
    async def _add(call: ServiceCall):
        entry = next((e for e in hass.config_entries.async_entries(DOMAIN)), None)
        if not entry:
            return
        packages = dict(entry.options.get(CONF_PACKAGES, {}))
        pkg = {
            "carrier": call.data["carrier"],
            "number": call.data["number"].strip(),
            "name": (call.data.get("name") or "").strip()
        }
        packages[pkg["number"]] = pkg
        hass.config_entries.async_update_entry(entry, options={CONF_PACKAGES: packages})

    async def _remove(call: ServiceCall):
        entry = next((e for e in hass.config_entries.async_entries(DOMAIN)), None)
        if not entry:
            return
        packages = dict(entry.options.get(CONF_PACKAGES, {}))
        n = call.data["number"].strip()
        packages.pop(n, None)
        hass.config_entries.async_update_entry(entry, options={CONF_PACKAGES: packages})

    hass.services.async_register(DOMAIN, "add_package", _add)
    hass.services.async_register(DOMAIN, "remove_package", _remove)
