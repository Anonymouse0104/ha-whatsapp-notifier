from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .chat_id import accepts, normalize
from .const import CONF_CHAT_ID, CONF_ONLY_REPLIES, DOMAIN, SIGNAL_MESSAGE, SIGNAL_STATUS
from .entity import Base

STATES = ["connected", "connecting", "pairing_required", "logged_out", "error", "bridge_unreachable"]


async def async_setup_entry(hass, entry, async_add_entities):
    bridge = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StatusSensor(entry, bridge, "status")])
    for sub in entry.subentries.values():
        async_add_entities([ChatSensor(entry, bridge, "last_message", sub)], config_subentry_id=sub.subentry_id)


class StatusSensor(Base, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATES

    @property
    def native_value(self):
        s = self.bridge.status
        return s if s in STATES else "error"

    @property
    def extra_state_attributes(self):
        # includes pairing_code while pairing_required
        return self.bridge.attrs

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_STATUS, self.async_write_ha_state))


class ChatSensor(Base, SensorEntity):
    """Text of the last message in this chat (max 255 chars); full details are attributes.

    Same text twice in a row keeps the state while the `id` attribute changes.
    shortcut: starts empty after a restart, add RestoreEntity if people need it to survive.
    """

    def __init__(self, entry, bridge, key, subentry) -> None:
        super().__init__(entry, bridge, key, subentry)
        self._chat = normalize(subentry.data[CONF_CHAT_ID])
        self._only_replies = subentry.data.get(CONF_ONLY_REPLIES, False)
        self._last: dict | None = None

    @property
    def native_value(self):
        return self._last["text"][:255] if self._last else None

    @property
    def extra_state_attributes(self):
        return self._last or {}

    @callback
    def _on_message(self, m: dict) -> None:
        if not accepts(self._chat, self._only_replies, m):
            return
        self._last = m
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_MESSAGE, self._on_message))
