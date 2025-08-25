# Package Tracker (PL) — Home Assistant Custom Integration

**Tracks InPost and DHL (Poland) packages**, polls every **7 minutes**, creates:
- One sensor per package with **detailed status**.
- A second sensor per package with a **normalized short status** (`Label created` / `In transit` / `In delivery Today` / `Delivered`).
- An aggregate sensor **`Packages Delivering Today`** with attributes:
  - `courier_today` — number of **courier** (DHL) packages expected **today**
  - `parcel_locker_today` — number of **parcel locker** (InPost) packages expected **today**

Includes a **Web UI** (left sidebar panel) to add/remove packages without YAML.

> DHL is scraped from the public tracking page the user provided. InPost uses the public ShipX tracking endpoint.

## Installation

### Option A — Manual (quickest)
1. Unzip to: `<config>/custom_components/packagetracker/` (create folders if needed).
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Integrations → Add Integration** and search for **Package Tracker (PL)**.
4. After install, a **Package Tracker** panel appears in the sidebar. Use it to add packages.

### Option B — HACS (Custom Repository)
This repo is HACS-ready. Add it as a **Custom Repository** in HACS (type: *Integration*), then install.
> HACS requires a URL; if you're using this zip, upload it to your own repo first.

## Usage
- Add packages via the **Package Tracker** panel or via **Settings → Integrations → Package Tracker → Configure** (bulk add textarea).
- Sensors names are based on your friendly name (or the tracking number).

## Notes
- Polling interval is **7 minutes**.
- Short statuses are inferred heuristically from provider messages.
- DHL site structure may change; if scraping stops working, open an issue.
- Requires Internet access from Home Assistant to provider endpoints.

## Privacy
All requests are made directly from your Home Assistant to InPost/DHL. No third-party server is involved.