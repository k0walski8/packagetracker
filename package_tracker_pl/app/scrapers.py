import re, json, requests
from datetime import datetime, date
from typing import Tuple, Optional

DHL_URL = "https://www.dhl.com/pl-pl/home/sledzenie-przesylek.html?tracking-id={number}&submit=1&inputsource=marketingstage"
INPOST_URL = "https://api-shipx-pl.easypack24.net/v1/tracking/{number}"

UA = {"User-Agent": "Mozilla/5.0", "Accept-Language":"pl,en;q=0.8"}

def map_summary_from_text(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["doręczono", "dostarczono", "delivered"]):
        return "Delivered"
    if any(k in t for k in ["w doręczeniu", "kurier w trasie", "out for delivery"]):
        return "In delivery Today"
    if any(k in t for k in ["utworzono etykietę", "label created", "zarejestrowano przesyłkę"]):
        return "Label created"
    if any(k in t for k in ["w trasie", "przekazano", "sortowni", "on the way", "in transit"]):
        return "In transit"
    return "In transit"

def fetch_inpost(number: str) -> Tuple[str, Optional[date]]:
    url = INPOST_URL.format(number=number)
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    data = r.json()
    detail_text = None
    eta_today = None

    def _get(obj, keys, default=None):
        for k in keys:
            if isinstance(obj, dict) and k in obj:
                obj = obj[k]
            else:
                return default
        return obj

    details = data.get("tracking_details") or []
    if isinstance(details, list) and details:
        last = details[0]
        detail_text = last.get("status") or last.get("title") or json.dumps(last, ensure_ascii=False)
        eta = last.get("expected_delivery") or data.get("estimated_delivery_date") or data.get("forecasted_delivery")
        if eta:
            try:
                dt = datetime.fromisoformat(str(eta)[:19])
                if dt.date() == datetime.now().date():
                    eta_today = dt.date()
            except Exception:
                try:
                    dt2 = datetime.strptime(str(eta), "%Y-%m-%d").date()
                    if dt2 == datetime.now().date():
                        eta_today = dt2
                except Exception:
                    pass

    if not detail_text:
        for k in ["status", "status_title", "status-description", "statusDescription"]:
            if k in data:
                detail_text = str(data[k])
                break

    if not detail_text:
        detail_text = "Nie udało się odczytać statusu (InPost)"

    return detail_text, eta_today

def fetch_dhl(number: str) -> Tuple[str, Optional[date]]:
    url = DHL_URL.format(number=number)
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    html = r.text
    detail_text = None
    eta_today = None

    patterns = [
        r"(Doręczono|Dostarczono|Przesyłka została doręczona)",
        r"(W doręczeniu|Kurier w trasie|Out for delivery)",
        r"(W trasie|W sortowni|Przekazano do doręczenia)",
        r"(Utworzono etykietę|Label created|Zarejestrowano przesyłkę)",
    ]
    for p in patterns:
        m = re.search(p, html, flags=re.I)
        if m:
            detail_text = m.group(0)
            break

    if not detail_text:
        # Some DHL pages embed data in JSON; we keep it simple here.
        detail_text = "Nie udało się odczytać statusu (DHL); strona może wymagać JS"

    if re.search(r"(doręczenie.*dziś|dzisiaj|today)", html, flags=re.I):
        eta_today = datetime.now().date()

    return detail_text, eta_today

def summarize(detail: str, eta_today: Optional[date]) -> str:
    base = map_summary_from_text(detail or "")
    return base
