from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "packagetracker"
NAME = "Package Tracker (PL)"
PLATFORMS: list[Platform] = [Platform.SENSOR]
STORAGE_VERSION = 1

SIGNAL_NEW_PACKAGE = f"{DOMAIN}_new_package"
SIGNAL_REMOVED_PACKAGE = f"{DOMAIN}_removed_package"

# Normalized short statuses
SHORT_CREATED = "Label created"
SHORT_TRANSIT = "In transit"
SHORT_OUT_FOR_DELIVERY_TODAY = "In delivery Today"
SHORT_DELIVERED = "Delivered"

PROVIDER_DHL = "dhl"
PROVIDER_INPOST = "inpost"