import json
import paho.mqtt.client as mqtt
from typing import Optional
from models import MQTTConfig, Package

class MQTTManager:
    def __init__(self, cfg: MQTTConfig):
        self.cfg = cfg
        self.client: Optional[mqtt.Client] = None
        self.connected = False

    def connect(self):
        if not self.cfg.host:
            return
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        if self.cfg.username:
            self.client.username_pw_set(self.cfg.username, self.cfg.password or None)

        def on_connect(client, userdata, flags, reason_code, properties=None):
            self.connected = (reason_code == 0)

        self.client.on_connect = on_connect
        try:
            self.client.connect(self.cfg.host, self.cfg.port, 60)
            self.client.loop_start()
        except Exception:
            self.connected = False

    def stop(self):
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
        except Exception:
            pass
        self.connected = False

    def _pub(self, topic: str, payload: str, retain=True):
        if not self.client or not self.connected:
            return
        self.client.publish(topic, payload, retain=retain)

    def _discovery_topic(self, kind: str, unique_id: str) -> str:
        return f"homeassistant/{kind}/{unique_id}/config"

    def publish_sensor_discovery(self, unique_id: str, name: str, state_topic: str, device_id: str, device_name: str):
        cfg = {
            "name": name,
            "state_topic": state_topic,
            "unique_id": unique_id,
            "device": {
                "identifiers": [device_id],
                "name": device_name,
                "manufacturer": "Community",
                "model": "Advanced Package Tracker (PL)"
            },
            "icon": "mdi:package-variant"
        }
        self._pub(self._discovery_topic("sensor", unique_id), json.dumps(cfg))

    def publish_state(self, topic: str, value: str):
        self._pub(topic, value)

    def publish_counters_discovery(self, unique_id: str, name: str, state_topic: str):
        cfg = {
            "name": name,
            "state_topic": state_topic,
            "unique_id": unique_id,
            "device": {
                "identifiers": ["package_tracker_group"],
                "name": "Packages (Today)",
                "manufacturer": "Community",
                "model": "Advanced Package Tracker (PL)"
            },
            "icon": "mdi:truck-delivery"
        }
        self._pub(self._discovery_topic("sensor", unique_id), json.dumps(cfg))

    def ensure_package_discovery(self, pkg: Package):
        base = self.cfg.base_topic
        device_id = f"pkg_{pkg.id}"
        device_name = pkg.label or f"{pkg.carrier.upper()} {pkg.number}"
        detail_uid = f"{pkg.id}_detail"
        detail_topic = f"{base}/{pkg.id}/status_detail"
        self.publish_sensor_discovery(detail_uid, f"{device_name} - Detailed", detail_topic, device_id, device_name)
        summary_uid = f"{pkg.id}_summary"
        summary_topic = f"{base}/{pkg.id}/status_summary"
        self.publish_sensor_discovery(summary_uid, f"{device_name} - Summary", summary_topic, device_id, device_name)

    def ensure_global_discovery(self, base_topic: str):
        self.publish_counters_discovery("packages_today_courier", "Courier packages arriving today", f"{base_topic}/today/courier")
        self.publish_counters_discovery("packages_today_locker", "Parcel locker packages arriving today", f"{base_topic}/today/locker")
