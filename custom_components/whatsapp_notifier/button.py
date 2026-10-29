from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import Base


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SendTestButton(entry, hass.data[DOMAIN][entry.entry_id], "test_message")])


class SendTestButton(Base, ButtonEntity):
    async def async_press(self) -> None:
        chat = self.bridge.default_chat()
        if not chat:
            raise HomeAssistantError("No default chat configured (integration options)")
        await self.bridge.send(chat, "Test message from Home Assistant")
