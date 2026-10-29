from __future__ import annotations

import voluptuous as vol
from aiohttp import ClientTimeout
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .chat_id import normalize
from .const import CONF_CHAT_ID, CONF_DEFAULT_CHAT, CONF_ONLY_REPLIES, CONF_TOKEN, DOMAIN, SUBENTRY_CHAT


class WhatsAppConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return WhatsAppOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_CHAT: ChatSubentryFlow}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            url = f"http://{user_input[CONF_HOST]}:{user_input[CONF_PORT]}/status"
            token = user_input.get(CONF_TOKEN, "")
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            try:
                async with async_get_clientsession(self.hass).get(url, headers=headers, timeout=ClientTimeout(total=10)) as r:
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


def _chat_schema(name="", chat_id="", only_replies=False) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=name): str,
            vol.Required(CONF_CHAT_ID, default=chat_id): str,
            vol.Required(CONF_ONLY_REPLIES, default=only_replies): bool,
        }
    )


class ChatSubentryFlow(ConfigSubentryFlow):
    """One chat (person or group): its own device with a notify entity and a last-message sensor."""

    @staticmethod
    def _chat(user_input: dict) -> tuple[str | None, dict[str, str]]:
        try:
            return normalize(user_input[CONF_CHAT_ID]), {}
        except ValueError:
            return None, {CONF_CHAT_ID: "invalid_chat_id"}

    async def async_step_user(self, user_input=None) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            chat, errors = self._chat(user_input)
            if chat and any(s.unique_id == chat for s in self._get_entry().subentries.values()):
                return self.async_abort(reason="already_configured")
            if chat:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={CONF_CHAT_ID: user_input[CONF_CHAT_ID], CONF_ONLY_REPLIES: user_input[CONF_ONLY_REPLIES]},
                    unique_id=chat,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_chat_schema(), user_input),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None) -> SubentryFlowResult:
        sub = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            chat, errors = self._chat(user_input)
            if chat:
                return self.async_update_and_abort(
                    self._get_entry(),
                    sub,
                    unique_id=chat,
                    title=user_input[CONF_NAME],
                    data_updates={CONF_CHAT_ID: user_input[CONF_CHAT_ID], CONF_ONLY_REPLIES: user_input[CONF_ONLY_REPLIES]},
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_chat_schema(sub.title, sub.data[CONF_CHAT_ID], sub.data.get(CONF_ONLY_REPLIES, False)),
            errors=errors,
        )
