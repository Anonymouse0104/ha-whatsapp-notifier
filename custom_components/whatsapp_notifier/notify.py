from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_CHAT_ID, DOMAIN
from .entity import Base


async def async_setup_entry(hass, entry, async_add_entities):
    bridge = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Notify(entry, bridge, "notify")])
    for sub in entry.subentries.values():
        async_add_entities([Notify(entry, bridge, "notify", sub)], config_subentry_id=sub.subentry_id)


class Notify(Base, NotifyEntity):
    """Sends to this chat, or to the default chat for the bridge device's entity."""

    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry, bridge, key, subentry=None) -> None:
        super().__init__(entry, bridge, key, subentry)
        self._subentry = subentry

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        chat = self._subentry.data[CONF_CHAT_ID] if self._subentry else self.bridge.default_chat()
        if not chat:
            raise HomeAssistantError("No default chat configured (integration options)")
        await self.bridge.send(chat, f"{title}\n{message}" if title else message)
