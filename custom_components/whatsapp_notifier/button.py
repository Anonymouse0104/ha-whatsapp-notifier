from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_CHAT_ID, DOMAIN
from .entity import Base


async def async_setup_entry(hass, entry, async_add_entities):
    bridge = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SendTestButton(entry, bridge, "test_message")])
    for sub in entry.subentries.values():
        async_add_entities([SendTestButton(entry, bridge, "test_message", sub)], config_subentry_id=sub.subentry_id)


class SendTestButton(Base, ButtonEntity):
    """Test message to this chat, or to the default chat for the bridge device's button."""

    def __init__(self, entry, bridge, key, subentry=None) -> None:
        super().__init__(entry, bridge, key, subentry)
        self._subentry = subentry

    async def async_press(self) -> None:
        chat = self._subentry.data[CONF_CHAT_ID] if self._subentry else self.bridge.default_chat()
        if not chat:
            raise HomeAssistantError("No default chat configured (integration options)")
        await self.bridge.send(chat, "Test message from Home Assistant")
