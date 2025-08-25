from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, NAME

class PackageTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Package Tracker (PL)."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial step; there's nothing to configure at setup time."""
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PackageTrackerOptionsFlow(config_entry)


class PackageTrackerOptionsFlow(config_entries.OptionsFlow):
    """Options flow to add/remove packages from UI (as a convenience)."""

    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        """Show instructions and allow simple bulk add via textarea."""
        if user_input is not None:
            # We will store bulk text into the options; the integration uses the storage,
            # but keeping a copy here helps with UI edits.
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Optional("bulk_add_help", default=(
                "One per line: provider,tracking_number,optional friendly name. "
                "Provider is 'dhl' or 'inpost'. Example:\n"
                "inpost,1234567890,Buty Zalando\n"
                "dhl,JD014600006000000000,Router"
            )): str,
            vol.Optional("bulk_add_lines", default=""): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)