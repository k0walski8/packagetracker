import json, os, threading, time, uuid
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from models import Package, PackageIn, Settings, MQTTConfig
from mqtt_client import MQTTManager
from scrapers import fetch_inpost, fetch_dhl, summarize

DATA_DIR = "/data"
PKG_FILE = os.path.join(DATA_DIR, "packages.json")

app = FastAPI(title="Advanced Package Tracker (PL)")
app.mount("/static", StaticFiles(directory="static"), name="static")

state: Dict = {
    "settings": Settings(),
    "packages": [],
    "last_poll": None,
    "polling": False
}

mqtt: MQTTManager = MQTTManager(state["settings"].mqtt)

def _save():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PKG_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "settings": state["settings"].model_dump(),
            "packages": [p.model_dump() for p in state["packages"]]
        }, f, ensure_ascii=False, indent=2, default=str)

def _load():
    if os.path.exists(PKG_FILE):
        try:
            with open(PKG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            state["settings"] = Settings(**data.get("settings", {}))
            state["packages"] = [Package(**p) for p in data.get("packages", [])]
        except Exception:
            pass

def _read_addon_options_into_settings():
    opts_path = "/data/options.json"
    if os.path.exists(opts_path):
        try:
            with open(opts_path, "r", encoding="utf-8") as f:
                opts = json.load(f)
            s = state["settings"]
            s.poll_interval_minutes = int(opts.get("poll_interval_minutes", s.poll_interval_minutes))
            s.mqtt = MQTTConfig(
                host=opts.get("mqtt_host", s.mqtt.host),
                port=int(opts.get("mqtt_port", s.mqtt.port)),
                username=opts.get("mqtt_username", s.mqtt.username),
                password=opts.get("mqtt_password", s.mqtt.password),
                base_topic=opts.get("mqtt_base_topic", s.mqtt.base_topic),
            )
            state["settings"] = s
        except Exception:
            pass

@app.on_event("startup")
def startup_event():
    _read_addon_options_into_settings()
    _load()
    global mqtt
    mqtt = MQTTManager(state["settings"].mqtt)
    mqtt.connect()
    mqtt.ensure_global_discovery(state["settings"].mqtt.base_topic)
    for p in state["packages"]:
        mqtt.ensure_package_discovery(p)
    t = threading.Thread(target=poller_loop, daemon=True)
    t.start()

def poll_once():
    today_courier = 0
    today_locker = 0
    for i, pkg in enumerate(state["packages"]):
        try:
            if pkg.carrier == "inpost":
                detail, eta_today = fetch_inpost(pkg.number)
            elif pkg.carrier == "dhl":
                detail, eta_today = fetch_dhl(pkg.number)
            else:
                detail, eta_today = ("Nieznany przewoźnik", None)
            summary = summarize(detail, eta_today)
            pkg.detailed_status = detail
            pkg.summary_status = summary
            pkg.last_update = datetime.utcnow()
            pkg.history.insert(0, {"ts": datetime.utcnow().isoformat(), "detail": detail, "summary": summary})
            state["packages"][i] = pkg

            base = state["settings"].mqtt.base_topic
            mqtt.ensure_package_discovery(pkg)
            mqtt.publish_state(f"{base}/{pkg.id}/status_detail", pkg.detailed_status or "")
            mqtt.publish_state(f"{base}/{pkg.id}/status_summary", pkg.summary_status or "")

            if summary == "In delivery Today":
                if pkg.carrier == "dhl":
                    today_courier += 1
                elif pkg.carrier == "inpost":
                    today_locker += 1

        except Exception as e:
            err = f"Błąd pobierania: {e}"
            pkg.detailed_status = (pkg.detailed_status or "") + f" | {err}"
            pkg.last_update = datetime.utcnow()

    base = state["settings"].mqtt.base_topic
    mqtt.publish_state(f"{base}/today/courier", str(today_courier))
    mqtt.publish_state(f"{base}/today/locker", str(today_locker))

    state["last_poll"] = datetime.utcnow()
    _save()

def poller_loop():
    while True:
        try:
            state["polling"] = True
            poll_once()
        finally:
            state["polling"] = False
        interval = max(1, int(state["settings"].poll_interval_minutes)) * 60
        time.sleep(interval)

@app.get("/")
def index():
    return FileResponse("static/index.html")

@app.get("/api/packages")
def get_packages():
    return JSONResponse([p.model_dump() for p in state["packages"]])

@app.post("/api/packages")
def add_package(pkg: PackageIn):
    number = pkg.number.strip()
    if not number:
        raise HTTPException(400, "Tracking number required")
    pid = uuid.uuid4().hex[:10]
    new_pkg = Package(
        id=pid, carrier=pkg.carrier, number=number,
        label=pkg.label, added_at=datetime.utcnow(), history=[]
    )
    state["packages"].append(new_pkg)
    _save()
    mqtt.ensure_package_discovery(new_pkg)
    return new_pkg

@app.delete("/api/packages/{pid}")
def delete_package(pid: str):
    before = len(state["packages"])
    state["packages"] = [p for p in state["packages"] if p.id != pid]
    if len(state["packages"]) == before:
        raise HTTPException(404, "Not found")
    _save()
    return {"ok": True}

@app.get("/api/settings")
def get_settings():
    return state["settings"].model_dump()

@app.post("/api/settings")
def set_settings(s: Settings):
    state["settings"] = s
    _save()
    mqtt.stop()
    new_mgr = MQTTManager(s.mqtt)
    new_mgr.connect()
    global mqtt
    mqtt = new_mgr
    mqtt.ensure_global_discovery(s.mqtt.base_topic)
    for p in state["packages"]:
        mqtt.ensure_package_discovery(p)
    return {"ok": True}

@app.post("/api/trigger-poll")
def trigger_poll():
    poll_once()
    return {"ok": True, "last_poll": state["last_poll"].isoformat() if state["last_poll"] else None}
