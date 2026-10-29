from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_STATUS
from .entity import Base

STATES = ["connected", "connecting", "pairing_required", "logged_out", "error", "bridge_unreachable"]


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([StatusSensor(entry, hass.data[DOMAIN][entry.entry_id], "status")])


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
