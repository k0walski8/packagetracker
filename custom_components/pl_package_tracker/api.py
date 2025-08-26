from __future__ import annotations
import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from aiohttp.client import ClientSession
from bs4 import BeautifulSoup

DHL_URL = "https://www.dhl.com/pl-pl/home/sledzenie-przesylek.html?tracking-id={number}"
INPOST_URL = "https://api-shipx-pl.easypack24.net/v1/tracking/{number}"

def _norm(s: Optional[str]) -> str:
    return (s or "").strip()

def _short_from_detail(detail: str) -> str:
    t = detail.lower()
    # Delivered
    if any(k in t for k in ["delivered", "doręczono", "odebrano", "dostarczono"]):
        return "Delivered"
    # Out for delivery (today)
    if any(k in t for k in ["out_for_delivery", "w doręczeniu", "kurier w drodze", 
                           "dzisiaj doręczenie", "przekazano do doręczenia", "in delivery"]):
        return "In delivery Today"
    # Label created / registered
    if any(k in t for k in ["created", "confirmed", "utworzono", "przygotowana przez nadawcę",
                           "zarejestrowano", "nadanie zarejestrowane"]):
        return "Label created"
    # Transit / processing
    return "In transit"

async def fetch_dhl(session: ClientSession, number: str) -> Dict[str, Any]:
    url = DHL_URL.format(number=number)
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    }
    
    async with session.get(url, headers=headers) as resp:
        text = await resp.text()
    soup = BeautifulSoup(text, "html.parser")

    # Try to find any obvious status text
    status_text = ""
    
    # Check tracking status elements
    status_elements = soup.select('.tracking-status, .status-text, .shipment-status')
    for element in status_elements:
        status_text = _norm(element.get_text(" ", strip=True))
        if status_text:
            break
            
    if not status_text:
        # Alternative search for status in document
        patterns = [
            r"(Doręczono|W doręczeniu|W tranzycie|Nadanie|Przesyłka w drodze)",
            r"(Delivered|Out for delivery|In transit|Shipment picked up)",
            r"Status:?\s*([^<>\n]+)"
        ]
        
        for pattern in patterns:
            m = re.search(pattern, text, re.I)
            if m:
                status_text = m.group(1)
                break

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

    # Map status names to their titles
    status_map = {
        "created": "Przesyłka utworzona",
        "confirmed": "Przygotowana przez Nadawcę",
        "dispatched_by_sender": "Paczka nadana w automacie Paczkomat",
        "collected_from_sender": "Odebrana od klienta",
        "taken_by_courier": "Odebrana od Nadawcy",
        "adopted_at_source_branch": "Przyjęta w oddziale InPost",
        "sent_from_source_branch": "W trasie",
        "adopted_at_sorting_center": "Przyjęta w Sortowni",
        "sent_from_sorting_center": "Wysłana z Sortowni",
        "adopted_at_target_branch": "Przyjęta w Oddziale Docelowym",
        "out_for_delivery": "Przekazano do doręczenia",
        "ready_to_pickup": "Umieszczona w automacie Paczkomat",
        "delivered": "Dostarczona",
        "returned_to_sender": "Zwrot do nadawcy",
        "avizo": "Powrót do oddziału",
        "canceled": "Anulowano etykietę",
        "undelivered": "Przekazanie do magazynu przesyłek niedoręczalnych",
        "stack_in_box_machine": "Paczka magazynowana w tymczasowym automacie",
        "stack_in_customer_service_point": "Paczka magazynowana w PaczkoPunkcie"
    }

    # Get status from tracking data
    status = None
    for path in [["status"], ["tracking", "status"], ["status", "name"]]:
        curr = data
        for key in path:
            if isinstance(curr, dict) and key in curr:
                curr = curr[key]
            else:
                curr = None
                break
        if curr:
            status = curr
            break

    # Get detail text
    if status and status in status_map:
        detail = status_map[status]
    else:
        detail = data.get("status", {}).get("title", "Unknown status")

    short = _short_from_detail(detail)
    return {
        "carrier": "inpost",
        "number": number,
        "detail": detail,
        "short": short,
        "last_update": datetime.now(timezone.utc).isoformat()
    }
