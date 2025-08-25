
from __future__ import annotations
import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from aiohttp.client import ClientSession
from bs4 import BeautifulSoup

DHL_URL = "https://www.dhl.com/pl-pl/home/sledzenie-przesylek.html"
DHL_QUERY = {"tracking-id": None, "submit": "1", "inputsource": "marketingstage"}
INPOST_URL = "https://api-shipx-pl.easypack24.net/v1/tracking/{number}"

def _norm(s: Optional[str]) -> str:
    return (s or "").strip()

def _short_from_detail(detail: str) -> str:
    t = detail.lower()
    # Delivered
    if any(k in t for k in ["delivered", "doręczono", "odebrano", "dostarczono"]):
        return "Delivered"
    # Out for delivery (today)
    if any(k in t for k in ["out for delivery", "w doręczeniu", "kurier w drodze", "dzisiaj doręczenie", "dzisiaj"]):
        return "In delivery Today"
    # Label created / registered
    if any(k in t for k in ["label created", "przyjęto zlecenie", "utworzono etykietę", "zarejestrowano", "nadanie zarejestrowane"]):
        return "Label created"
    # Transit / processing
    return "In transit"

async def fetch_dhl(session: ClientSession, number: str) -> Dict[str, Any]:
    params = DHL_QUERY.copy()
    params["tracking-id"] = number
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    }
    async with session.get(DHL_URL, params=params, headers=headers) as resp:
        text = await resp.text()
    soup = BeautifulSoup(text, "html.parser")

    # Try to find any obvious status text
    status_text = ""
    # Known classes/ids tend to include 'status'
    for el in soup.find_all(lambda tag: tag.has_attr("class") and any("status" in c.lower() for c in tag["class"])):
        status_text = _norm(el.get_text(" ", strip=True))
        if status_text:
            break
    if not status_text:
        # Search whole document for keywords around 'Status'
        m = re.search(r"(Doręczono|W doręczeniu|W tranzycie|Nadanie|Przesyłka w drodze|Delivered|Out for delivery)", text, re.I)
        if m:
            status_text = m.group(1)

    if not status_text:
        status_text = "Unknown / parsing failed"

    short = _short_from_detail(status_text)
    return {
        "carrier": "dhl",
        "number": number,
        "detail": status_text,
        "short": short,
        "last_update": datetime.now(timezone.utc).isoformat()
    }

async def fetch_inpost(session: ClientSession, number: str) -> Dict[str, Any]:
    url = INPOST_URL.format(number=number)
    headers = {"User-Agent": "Mozilla/5.0"}
    async with session.get(url, headers=headers) as resp:
        if resp.status != 200:
            detail = f"HTTP {resp.status}"
            return {
                "carrier": "inpost",
                "number": number,
                "detail": detail,
                "short": _short_from_detail(detail),
                "last_update": datetime.now(timezone.utc).isoformat()
            }
        data = await resp.json(content_type=None)

    # Heuristics to get a readable detail line
    detail = ""
    # Many ShipX responses have 'status' or nested 'tracking' / 'status'
    for path in [
        ["status"],
        ["tracking", "status"],
        ["last_status", "status"],
        ["last_status", "title"],
        ["state"],
    ]:
        cur = data
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                cur = None
                break
        if isinstance(cur, str):
            detail = cur
            break

    # Fallback: look into events/operations arrays
    if not detail:
        for key in ["operations", "tracking_details", "events"]:
            arr = data.get(key)
            if isinstance(arr, list) and arr:
                last = arr[-1]
                for cand in ["status", "title", "description", "message"]:
                    if isinstance(last, dict) and isinstance(last.get(cand), str):
                        detail = last[cand]
                        break
            if detail:
                break

    if not detail:
        detail = "Unknown status"

    short = _short_from_detail(detail)
    return {
        "carrier": "inpost",
        "number": number,
        "detail": detail,
        "short": short,
        "last_update": datetime.now(timezone.utc).isoformat()
    }
