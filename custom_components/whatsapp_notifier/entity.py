from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class Base(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, bridge, key: str) -> None:
        self.bridge = bridge
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name="WhatsApp")
