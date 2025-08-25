from __future__ import annotations

import logging
import re
import json
from typing import Any, Dict

from homeassistant.components import frontend, http
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import re

def _local_slugify(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")

from homeassistant.helpers.dispatcher import async_dispatcher_send
from .const import DOMAIN, SIGNAL_NEW_PACKAGE, PROVIDER_DHL, PROVIDER_INPOST

_LOGGER = logging.getLogger(__name__)

PANEL_URL = "/packagetracker"
API_BASE = "/api/packagetracker"

def _validate_provider(p: str) -> str | None:
    p = (p or "").lower().strip()
    if p in (PROVIDER_DHL, PROVIDER_INPOST):
        return p
    return None

async def async_register_http_panel_and_routes(hass: HomeAssistant, entry: ConfigEntry):
    """Register a simple Panel (web UI) and API endpoints to manage packages."""
    # Serve the panel html at a fixed path
    hass.http.register_static_path(
        path=PANEL_URL,
        cache_headers=False,
        cors=True,
        file_path=hass.config.path(f"custom_components/{DOMAIN}/panel.html"),
    )

    # Register API routes
    hass.http.register_view(PackageListView(hass, entry))
    hass.http.register_view(PackageAddView(hass, entry))
    hass.http.register_view(PackageDeleteView(hass, entry))

    # Add sidebar panel (panel_iframe)
    if not hass.data.get(f"{DOMAIN}_panel_added"):
        hass.components.frontend.async_register_built_in_panel(
            component_name="iframe",
            sidebar_title="Package Tracker",
            sidebar_icon="mdi:package-variant",
            config={"url": PANEL_URL},
            require_admin=False,
        )
        hass.data[f"{DOMAIN}_panel_added"] = True


class PackageListView(HomeAssistantView):
    url = f"{API_BASE}/list"
    name = "packagetracker:list"
    requires_auth = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

    async def get(self, request):
        store = self.hass.data[DOMAIN][self.entry.entry_id]["store"]
        data = await store.async_load() or {}
        pkgs = data.get("packages", [])
        return self.json({"packages": pkgs})


class PackageAddView(HomeAssistantView):
    url = f"{API_BASE}/add"
    name = "packagetracker:add"
    requires_auth = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

    async def post(self, request):
        try:
            payload = await request.json()
        except Exception:
            return self.json_message("Invalid JSON", status_code=422)
        provider = _validate_provider(payload.get("provider"))
        tracking = (payload.get("tracking_number") or "").strip()
        name = (payload.get("name") or "").strip()

        if not provider or not tracking:
            return self.json_message("provider must be 'dhl' or 'inpost' and tracking_number required", status_code=422)

        pkg_id = _local_slugify(f"{provider}-{tracking}")
        store = self.hass.data[DOMAIN][self.entry.entry_id]["store"]
        data = await store.async_load() or {}
        pkgs = data.get("packages", [])

        if any(p.get("id") == pkg_id for p in pkgs):
            return self.json_message("Package already exists", status_code=422)

        pkg = {
            "id": pkg_id,
            "provider": provider,
            "tracking_number": tracking,
            "name": name,
        }
        pkgs.append(pkg)
        data["packages"] = pkgs
        await store.async_save(data)

        # Notify sensors to add entities dynamically
        self.hass.bus.async_fire(SIGNAL_NEW_PACKAGE, {"package": pkg})

        # Trigger refresh
        coordinator = self.hass.data[DOMAIN][self.entry.entry_id]["coordinator"]
        await coordinator.async_request_refresh()

        return self.json({"ok": True, "package": pkg})


class PackageDeleteView(HomeAssistantView):
    url = f"{API_BASE}/delete"
    name = "packagetracker:delete"
    requires_auth = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

    async def post(self, request):
        try:
            payload = await request.json()
        except Exception:
            return self.json_message("Invalid JSON", status_code=422)
        provider = _validate_provider(payload.get("provider"))
        tracking = (payload.get("tracking_number") or "").strip()

        if not provider or not tracking:
            return self.json_message("provider and tracking_number required", status_code=422)

        pkg_id = _local_slugify(f"{provider}-{tracking}")
        store = self.hass.data[DOMAIN][self.entry.entry_id]["store"]
        data = await store.async_load() or {}
        pkgs = data.get("packages", [])
        new_pkgs = [p for p in pkgs if p.get("id") != pkg_id]
        if len(new_pkgs) == len(pkgs):
            return self.json_message("Not found", status_code=422)

        data["packages"] = new_pkgs
        await store.async_save(data)

        # Trigger refresh
        coordinator = self.hass.data[DOMAIN][self.entry.entry_id]["coordinator"]
        await coordinator.async_request_refresh()

        return self.json({"ok": True})