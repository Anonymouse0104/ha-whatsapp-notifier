from homeassistant.components.notify import NotifyEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import Base


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([WhatsAppNotify(entry, hass.data[DOMAIN][entry.entry_id], "notify")])


class WhatsAppNotify(Base, NotifyEntity):
    """Sends to the default chat. For another chat use whatsapp_notifier.send_message."""

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        chat = self.bridge.default_chat()
        if not chat:
            raise HomeAssistantError("No default chat configured (integration options)")
        await self.bridge.send(chat, f"{title}\n{message}" if title else message)
