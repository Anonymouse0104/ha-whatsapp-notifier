from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_MESSAGE, SIGNAL_STATUS
from .entity import Base

STATES = ["connected", "connecting", "pairing_required", "logged_out", "error", "bridge_unreachable"]


async def async_setup_entry(hass, entry, async_add_entities):
    bridge = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StatusSensor(entry, bridge, "status"), LastMessageSensor(entry, bridge, "last_message")])


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


class LastMessageSensor(Base, SensorEntity):
    """Text of the last received message (max 255 chars); the full message and sender are attributes.

    Same text twice in a row keeps the state; the `id` attribute still changes, so trigger on the event or any change.
    """

    @property
    def native_value(self):
        m = self.bridge.last_message
        return m["text"][:255] if m else None

    @property
    def extra_state_attributes(self):
        return self.bridge.last_message or {}

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_MESSAGE, self.async_write_ha_state))
