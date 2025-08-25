from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN, NAME


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Minimal config flow: single confirm step that creates the entry."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})
        # Show an empty form with just a Submit button
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))