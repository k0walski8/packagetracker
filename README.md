
# Polish Package Tracker (DHL + InPost) — Home Assistant Custom Integration

**No MQTT, no add-on required.** Add it via **Settings → Devices & Services → + Add Integration → Polish Package Tracker**.
You can add/remove many packages from a friendly options flow.

## Features
- Tracks many DHL (courier) and InPost (parcel locker) packages.
- Polls every **7 minutes**.
- Creates **two sensors per package**:
  - `… – detailed status` (full text from the carrier)
  - `… – status` (short state: *Label created* / *In transit* / *In delivery Today* / *Delivered*)
- Adds an **aggregate sensor**: `Packages arriving today` with attributes:
  - `courier_today`
  - `parcel_locker_today`
- Uses carrier sources you provided:
  - DHL (scraping): `https://www.dhl.com/pl-pl/home/sledzenie-przesylek.html?tracking-id=...`
  - InPost (API): `https://api-shipx-pl.easypack24.net/v1/tracking/...`

> **Note:** DHL’s public website can change at any time. The parser is defensive, but if it ever fails to parse
the detailed status, the short status may still work.

## Install (manual ZIP)
1. Download the ZIP from your Chat: **pl_package_tracker.zip**.
2. Unzip to `config/custom_components/pl_package_tracker/`.
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → + Add Integration → Polish Package Tracker** and add your first package.
   Use **Configure** to add/remove more.

## Privacy
All requests go directly from your Home Assistant to the official carrier endpoints; no third-party servers.

## Uninstall
Remove the integration from Devices & Services; the sensors will be removed automatically.
