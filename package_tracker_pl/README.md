# Advanced Package Tracker (PL) — Home Assistant Add-on

Tracks DHL (Poland) and InPost packages, with a web UI (Ingress) for adding/removing tracking numbers,
MQTT Discovery sensors for each package (detailed + summary), and two global counters for today's deliveries:
- **Courier packages arriving today** (DHL)
- **Parcel locker packages arriving today** (InPost)

## Installation (as custom repository)
1. In **Settings → Add-ons → Add-on Store**, click the three dots → **Repositories**.
2. Add the URL where this repository is hosted (or install locally by placing this folder in `/addons`).
3. Find **Advanced Package Tracker (PL)** in the store, install, and start.
4. Open the add-on and use the **Ingress** Web UI to configure MQTT and add package numbers.

> Note: Inclusion in the official built-in repository is controlled by Home Assistant maintainers. This add-on is fully compatible with the Supervisor and the official Add-on Store as a custom repository.

## Configuration
Via add-on options or the web UI:
- `poll_interval_minutes` — default **7** (as requested).
- `mqtt_host`, `mqtt_port`, `mqtt_username`, `mqtt_password`, `mqtt_base_topic` — used for MQTT Discovery and state updates.

### Entities created (via MQTT Discovery)
For each package:
- `<label or CARRIER NUMBER> - Detailed` → full status text
- `<label or CARRIER NUMBER> - Summary` → one of: **Label created** / **In transit** / **In delivery Today** / **Delivered**

Global counters:
- `Courier packages arriving today`
- `Parcel locker packages arriving today`

## Carriers
- **DHL (Poland)** — scraped from `https://www.dhl.com/pl-pl/home/sledzenie-przesylek.html?tracking-id=...`
- **InPost** — ShipX public tracking endpoint: `https://api-shipx-pl.easypack24.net/v1/tracking/{number}`

## Notes
- The DHL page may sometimes render content dynamically; the scraper uses best-effort extraction of key phrases.
  If parsing fails, the add-on keeps the previous status and tries again on the next cycle.
- Make sure you have an MQTT broker configured in Home Assistant (e.g., Mosquitto) so Discovery can create entities.

## License
MIT
