
from __future__ import annotations

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from .const import (
    DOMAIN, CONF_PACKAGES, CONF_CARRIER, CONF_NUMBER, CONF_NAME,
    CARRIER_DHL, CARRIER_INPOST
)

CARRIERS = { "DHL": CARRIER_DHL, "InPost": CARRIER_INPOST }

def _pkg_schema(defaults: dict | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema({
        vol.Required("carrier", default=defaults.get("carrier", CARRIER_DHL)): vol.In(list(CARRIERS.values())),
        vol.Required("number", default=defaults.get("number", "")): str,
        vol.Optional("name", default=defaults.get("name", "")): str,
    })

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors = {}
        if user_input is not None:
            # Store first package in options
            pkg = {
                "carrier": user_input["carrier"],
                "number": user_input["number"].strip(),
                "name": (user_input.get("name") or "").strip()
            }
            options = {CONF_PACKAGES: {pkg["number"]: pkg}}
            return self.async_create_entry(title="Polish Package Tracker", data={}, options=options)

        return self.async_show_form(step_id="user", data_schema=_pkg_schema(), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._entry = config_entry
        self._packages = dict(config_entry.options.get(CONF_PACKAGES, {}))

    async def async_step_init(self, user_input=None) -> FlowResult:
        return self.async_show_menu(step_id="init", menu_options=["add", "remove"])

    async def async_step_add(self, user_input=None) -> FlowResult:
        if user_input is not None:
            pkg = {
                "carrier": user_input["carrier"],
                "number": user_input["number"].strip(),
                "name": (user_input.get("name") or "").strip()
            }
            self._packages[pkg["number"]] = pkg
            return await self._save_and_exit()

        return self.async_show_form(step_id="add", data_schema=_pkg_schema())

    async def async_step_remove(self, user_input=None) -> FlowResult:
        numbers = list(self._packages.keys())
        if not numbers:
            return await self._save_and_exit()

        schema = vol.Schema({ vol.Required("numbers", default=[]): cv.multi_select({n: n for n in numbers}) })
        if user_input is not None:
            for n in user_input.get("numbers", []):
                self._packages.pop(n, None)
            return await self._save_and_exit()

        return self.async_show_form(step_id="remove", data_schema=schema)

    async def _save_and_exit(self) -> FlowResult:
        options = dict(self._entry.options)
        options[CONF_PACKAGES] = self._packages
        return self.async_create_entry(title="", data=options)
