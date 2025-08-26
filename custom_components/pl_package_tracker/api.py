from __future__ import annotations
import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from aiohttp.client import ClientSession
from bs4 import BeautifulSoup

DHL_URL = "https://www.dhl.com/pl-pl/home/sledzenie-przesylek.html?tracking-id={number}"
INPOST_URL = "https://api-shipx-pl.easypack24.net/v1/tracking/{number}"

def _norm(s: Optional[str]) -> str:
    return (s or "").strip()

def _short_from_detail(detail: str) -> str:
    t = detail.lower()
    # Delivered
    if any(k in t for k in [
        "delivered", 
        "doręczono", 
        "odebrano", 
        "dostarczono",
        "przesyłka doręczona do odbiorcy",
        "the shipment has been successfully delivered"
    ]):
        return "Delivered"
    
    # Out for delivery (today)
    if any(k in t for k in [
        "out_for_delivery", 
        "w doręczeniu", 
        "kurier w drodze", 
        "dzisiaj doręczenie", 
        "przekazano do doręczenia", 
        "in delivery",
        "przesyłka przekazana kurierowi do doręczenia",
        "the shipment has been loaded onto the delivery vehicle"
    ]):
        return "In delivery Today"
    
    # Label created / registered
    if any(k in t for k in [
        "created", 
        "confirmed", 
        "utworzono", 
        "przygotowana przez nadawcę",
        "zarejestrowano", 
        "nadanie zarejestrowane",
        "przesyłka przyjęta w terminalu nadawczym dhl"
    ]):
        return "Label created"
    
    # Transit / processing
    if any(k in t for k in [
        "przesyłka jest obsługiwana w centrum sortowania",
        "the shipment has been processed in the parcel center"
    ]):
        return "In transit"
    
    # Default case for any other status
    return "In transit"

async def fetch_dhl(session: ClientSession, number: str) -> Dict[str, Any]:
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Initialize the driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        # Navigate to the tracking page
        url = DHL_URL.format(number=number)
        driver.get(url)
        
        # Wait for and click the submit button
        submit_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".js--tracking--input-submit"))
        )
        submit_button.click()
        
        # Wait for status message element
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.c-tracking-result--status-copy-message'))
        )
        
        # Add debug logging
        print(f"Extracting status for DHL package {number}")
        
        # Get the page source after JavaScript execution
        text = driver.page_source
        
        # Debug: Log the relevant HTML section
        status_section = driver.find_elements(By.CSS_SELECTOR, '.c-tracking-result--section')
        if status_section:
            print("Found status section:", status_section[0].text)
        
        soup = BeautifulSoup(text, "html.parser")
        
        # Try to get status message and date
        status_text = ""
        date_text = ""
        
        # First try the main status message with more specific selector
        status_element = soup.select_one('.c-tracking-result--status-copy-message')
        if status_element:
            print("Found status element:", status_element.text)
            status_text = _norm(status_element.get_text(" ", strip=True))
            # Remove tracking number if present
            status_text = re.sub(r',\s*Kod nadania przesyłki:.*$', '', status_text)
            print("Cleaned status text:", status_text)
            
            # Try to get the date with more specific selector
            date_element = soup.select_one('.c-tracking-result--status-copy-date')
            if date_element:
                date_text = _norm(date_element.get_text(" ", strip=True))
                print("Found date:", date_text)
        else:
            print("Status element not found with primary selector")

        # If still no status, try alternative selectors
        if not status_text:
            print("Trying alternative selectors...")
            alt_selectors = [
                '.c-tracking-result--status h2',
                '.c-tracking-result--status-copy-message',
                '.tracking-status',
                '.status-text',
                '.shipment-status'
            ]
            
            for selector in alt_selectors:
                element = soup.select_one(selector)
                if element:
                    status_text = _norm(element.get_text(" ", strip=True))
                    print(f"Found status with selector {selector}:", status_text)
                    break
                    
        # Try regex patterns if still no status
        if not status_text:
            print("Trying regex patterns...")
            patterns = [
                # DHL specific patterns
                r"przesyłka jest obsługiwana w centrum sortowania",
                r"przesyłka przekazana kurierowi do doręczenia",
                r"przesyłka doręczona do odbiorcy",
                r"przesyłka przyjęta w terminalu nadawczym dhl",
                # ...existing patterns...
            ]
            
            for pattern in patterns:
                m = re.search(pattern, text, re.I)
                if m:
                    status_text = m.group(0)
                    print(f"Found status with pattern:", status_text)
                    break

        if not status_text:
            print("Failed to extract status")
            status_text = "Unknown / parsing failed"

        # Combine status and date if available
        detail = status_text
        if date_text:
            detail = f"{status_text} ({date_text})"
            
        print(f"Final status: {detail}")

    finally:
        # Always close the browser
        driver.quit()

    short = _short_from_detail(detail)
    return {
        "carrier": "dhl",
        "number": number,
        "detail": detail,
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
