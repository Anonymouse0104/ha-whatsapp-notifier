from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEFAULT_CHAT, CONF_TOKEN, DOMAIN


class WhatsAppConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return WhatsAppOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            url = f"http://{user_input[CONF_HOST]}:{user_input[CONF_PORT]}/status"
            token = user_input.get(CONF_TOKEN, "")
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            try:
                async with async_get_clientsession(self.hass).get(url, headers=headers, timeout=10) as r:
                    if r.status == 401:
                        errors["base"] = "invalid_auth"
                    else:
                        r.raise_for_status()
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            if not errors:
                await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
                self._abort_if_unique_id_configured()
                data = {k: v for k, v in user_input.items() if k != CONF_DEFAULT_CHAT}
                return self.async_create_entry(
                    title="WhatsApp",
                    data=data,
                    options={CONF_DEFAULT_CHAT: user_input.get(CONF_DEFAULT_CHAT, "")},
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="homeassistant.local"): str,
                vol.Required(CONF_PORT, default=8099): int,
                vol.Optional(CONF_TOKEN, default=""): str,
                vol.Optional(CONF_DEFAULT_CHAT, default=""): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class WhatsAppOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_DEFAULT_CHAT, "")
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema({vol.Optional(CONF_DEFAULT_CHAT, default=current): str})
        )
