from __future__ import annotations

import asyncio
import logging
from datetime import timedelta, datetime
from typing import Any, Dict, List

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import now as ha_now, as_local
from homeassistant.helpers.storage import Store
from homeassistant.const import CONF_NAME

import aiohttp
from bs4 import BeautifulSoup

from .const import (
    DOMAIN,
    PROVIDER_DHL,
    PROVIDER_INPOST,
    SHORT_CREATED,
    SHORT_DELIVERED,
    SHORT_OUT_FOR_DELIVERY_TODAY,
    SHORT_TRANSIT,
)

_LOGGER = logging.getLogger(__name__)


class PackageUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator that polls both InPost and DHL every 7 minutes."""

    def __init__(self, hass: HomeAssistant, store: Store) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=7),
        )
        self._store = store
        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _async_get_packages(self) -> List[Dict[str, Any]]:
        data = await self._store.async_load() or {}
        return data.get("packages", [])

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data for all packages."""
        try:
            pkgs = await self._async_get_packages()
            results = await asyncio.gather(
                *[self._fetch_package(p) for p in pkgs],
                return_exceptions=True,
            )
            out: Dict[str, Any] = {}
            for p, r in zip(pkgs, results):
                if isinstance(r, Exception):
                    _LOGGER.warning("Failed to fetch %s %s: %s", p.get("provider"), p.get("tracking_number"), r)
                    out[p["id"]] = {"error": str(r), "package": p}
                else:
                    out[p["id"]] = {**r, "package": p}
            # Add today's aggregate
            out["_aggregate_today"] = self._compute_today_counts(out)
            return out
        except Exception as err:
            raise UpdateFailed(str(err)) from err

    def _compute_today_counts(self, data: Dict[str, Any]) -> Dict[str, Any]:
        courier = 0
        locker = 0
        today = as_local(ha_now()).date()
        for key, v in data.items():
            if key.startswith("_"):
                continue
            pkg = v.get("package", {})
            provider = pkg.get("provider")
            is_today = v.get("out_for_delivery_today", False)
            delivered = v.get("short_status") == SHORT_DELIVERED
            # We count only ones expected today and not yet delivered
            if is_today and not delivered:
                if provider == PROVIDER_DHL:
                    courier += 1
                elif provider == PROVIDER_INPOST:
                    locker += 1
        return {
            "courier_today": courier,
            "parcel_locker_today": locker,
            "state": courier + locker,
            "as_of": as_local(ha_now()).isoformat()
        }

    async def _fetch_package(self, pkg: Dict[str, Any]) -> Dict[str, Any]:
        provider = pkg.get("provider")
        tracking_number = pkg.get("tracking_number")
        friendly_name = pkg.get("name") or tracking_number
        if provider == PROVIDER_INPOST:
            return await self._fetch_inpost(tracking_number, friendly_name)
        elif provider == PROVIDER_DHL:
            return await self._fetch_dhl(tracking_number, friendly_name)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _fetch_inpost(self, tracking: str, name: str) -> Dict[str, Any]:
        url = f"https://api-shipx-pl.easypack24.net/v1/tracking/{tracking}"
        headers = {
            "User-Agent": "HomeAssistant-PackageTracker/0.1",
            "Accept": "application/json",
        }
        async with self.session.get(url, headers=headers, timeout=30) as resp:
            if resp.status != 200:
                txt = await resp.text()
                raise RuntimeError(f"InPost HTTP {resp.status}: {txt[:200]}")
            js = await resp.json(content_type=None)
        # Try to extract a detailed string and normalized short status
        detailed = self._extract_inpost_detailed(js) or "Unknown"
        short, is_today = self._normalize_short_status(detailed, provider="inpost", raw=js)
        return {
            "friendly_name": name,
            "provider": "inpost",
            "tracking_number": tracking,
            "detailed_status": detailed,
            "short_status": short,
            "out_for_delivery_today": is_today,
            "last_update": as_local(ha_now()).isoformat(),
            "raw": js,
        }

    def _extract_inpost_detailed(self, js: Dict[str, Any]) -> str | None:
        # Common ShipX schema:
        # {
        #   "status": "delivered",
        #   "tracking_number": "...",
        #   "operations": {"status": {...}},
        #   "tracking_details": [{"status": "...", "origin_status": "...", "datetime": "...", "description": "..."}]
        # }
        candidates = []
        for key in ("description", "status", "origin_status"):
            v = js.get(key)
            if isinstance(v, str) and v.strip():
                candidates.append(v.strip())
        if isinstance(js.get("tracking_details"), list) and js["tracking_details"]:
            # take the latest item
            td = js["tracking_details"][0]
            for key in ("description", "status", "origin_status"):
                v = td.get(key)
                if isinstance(v, str) and v.strip():
                    candidates.insert(0, v.strip())
        return candidates[0] if candidates else None

    async def _fetch_dhl(self, tracking: str, name: str) -> Dict[str, Any]:
        # Scrape the public tracking page for Poland per user's URL
        url = f"https://www.dhl.com/pl-pl/home/sledzenie-przesylek.html?tracking-id={tracking}&submit=1&inputsource=marketingstage"
        headers = {
            "User-Agent": "HomeAssistant-PackageTracker/0.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        async with self.session.get(url, headers=headers, timeout=30) as resp:
            txt = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"DHL HTTP {resp.status}: {txt[:200]}")
        soup = BeautifulSoup(txt, "html.parser")
        # Try a few selectors that typically hold status text
        detailed = None
        # Look for elements with data-cq-component or status headings
        for selector in [
            "[data-cq-component*='tracking']",
            ".tracking-result .status",
            ".status__text",
            ".c-tracking-status__text",
            "h3",
            "p",
        ]:
            el = soup.select_one(selector)
            if el and el.get_text(strip=True):
                detailed = el.get_text(strip=True)
                break
        if not detailed:
            # Fallback: search by keywords in entire text
            text = soup.get_text(" ", strip=True)
            for keyword in ["Doręczona", "W doręczeniu", "Nadana", "W drodze", "Przesyłka", "Delivered", "Out for delivery", "Label created"]:
                if keyword.lower() in text.lower():
                    detailed = keyword
                    break
        if not detailed:
            detailed = "Unknown"

        short, is_today = self._normalize_short_status(detailed, provider="dhl", raw={"html": "omitted"})
        return {
            "friendly_name": name,
            "provider": "dhl",
            "tracking_number": tracking,
            "detailed_status": detailed,
            "short_status": short,
            "out_for_delivery_today": is_today,
            "last_update": as_local(ha_now()).isoformat(),
        }

    def _normalize_short_status(self, detailed: str, provider: str, raw: Any) -> tuple[str, bool]:
        """Normalize detailed text into one of 4 short statuses and whether it's due today."""
        t = (detailed or "").lower()

        # Heuristics
        # Delivered
        delivered_keywords = ["delivered", "doręczona", "doręczone", "odebrano", "picked up"]
        # Out for delivery today
        ofd_keywords = ["out for delivery", "w doręczeniu", "kurier wyruszył", "dzisiaj doręczenie", "dostarczymy dziś"]
        # Label created
        created_keywords = ["label created", "utworzono etykietę", "wygenerowano etykietę"]
        # In transit
        transit_keywords = ["in transit", "w drodze", "przesyłka w trasie", "przekazano do doręczenia", "nadana", "przyjęta w oddziale"]

        is_today = False

        # Try to detect explicit "today" hints
        for k in ofd_keywords:
            if k in t:
                is_today = True
                break

        # Try InPost JSON hints for ETA
        if isinstance(raw, dict) and provider == "inpost":
            # Many ShipX responses include expected_delivery or event dates.
            exp = raw.get("expected_delivery")
            if exp:
                try:
                    dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                    is_today = is_today or (as_local(dt).date() == as_local(ha_now()).date())
                except Exception:
                    pass
            # If latest event date is today and mentions delivery attempt
            if isinstance(raw.get("tracking_details"), list) and raw["tracking_details"]:
                desc = str(raw["tracking_details"][0].get("description", "")).lower()
                if any(k in desc for k in ofd_keywords):
                    is_today = True

        if any(k in t for k in delivered_keywords):
            return (SHORT_DELIVERED, False)
        if any(k in t for k in ofd_keywords):
            return (SHORT_OUT_FOR_DELIVERY_TODAY, True)
        if any(k in t for k in created_keywords):
            return (SHORT_CREATED, False)
        if any(k in t for k in transit_keywords):
            return (SHORT_TRANSIT, False)

        # Fallback
        return (SHORT_TRANSIT, False)