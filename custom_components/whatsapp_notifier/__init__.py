from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bridge import Bridge
from .const import CONF_CHAT_ID, CONF_DEFAULT_CHAT, CONF_TOKEN, DOMAIN

PLATFORMS = [Platform.NOTIFY, Platform.SENSOR, Platform.BUTTON]

SEND_SCHEMA = vol.Schema({vol.Required("message"): cv.string, vol.Optional("chat_id"): cv.string})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    d = entry.data
    bridge = Bridge(hass, async_get_clientsession(hass), d[CONF_HOST], d[CONF_PORT], d.get(CONF_TOKEN, ""))
    bridge.default_chat = lambda: entry.options.get(CONF_DEFAULT_CHAT, "")
    bridge.forward_chats = lambda: [sub.data[CONF_CHAT_ID] for sub in entry.subentries.values()]
    bridge.start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = bridge

    async def send_message(call: ServiceCall) -> dict:
        chat = call.data.get("chat_id") or bridge.default_chat()
        if not chat:
            raise HomeAssistantError("No chat_id given and no default chat configured")
        return {"message_id": await bridge.send(chat, call.data["message"])}

    # single-bridge setup: the service is bound to the first entry
    if not hass.services.has_service(DOMAIN, "send_message"):
        hass.services.async_register(
            DOMAIN, "send_message", send_message, SEND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
        )

    entry.async_on_unload(entry.add_update_listener(lambda h, e: h.config_entries.async_reload(e.entry_id)))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id).stop()
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "send_message")
    return ok
