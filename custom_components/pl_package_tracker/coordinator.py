
from __future__ import annotations
from datetime import timedelta
from typing import Any, Dict, List

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import UPDATE_INTERVAL_MIN, CONF_PACKAGES, CARRIER_DHL, CARRIER_INPOST
from .api import fetch_dhl, fetch_inpost

class PackageDataCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry):
        super().__init__(
            hass,
            hass.helpers.event.async_call_later.__self__,  # logger
            name="PL Package Tracker",
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MIN),
        )
        self.entry = entry

    @property
    def packages(self) -> List[dict]:
        return list(self.entry.options.get(CONF_PACKAGES, {}).values())

    async def _async_update_data(self) -> Dict[str, Any]:
        session = async_get_clientsession(self.hass)
        tasks = []
        for pkg in self.packages:
            carrier = pkg["carrier"]
            number = pkg["number"]
            if carrier == CARRIER_DHL:
                tasks.append(fetch_dhl(session, number))
            elif carrier == CARRIER_INPOST:
                tasks.append(fetch_inpost(session, number))

        results: Dict[str, Any] = {}
        for coro in tasks:
            try:
                data = await coro
                results[data["number"]] = data
            except Exception as err:  # noqa: BLE001
                # We keep the old data if any; mark error in detail
                num = getattr(coro, "__name__", "unknown")
                results[num] = {"detail": f"Error: {err}", "short": "In transit"}

        return results
