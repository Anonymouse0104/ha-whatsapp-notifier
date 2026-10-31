from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class Base(Entity):
    """Entity of the bridge device, or of a chat device when a subentry is given."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, bridge, key: str, subentry: ConfigSubentry | None = None) -> None:
        self.bridge = bridge
        self._attr_translation_key = key
        if subentry:
            self._attr_unique_id = f"{subentry.subentry_id}_{key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, subentry.subentry_id)}, name=subentry.title, via_device_id=bridge.device_id
            )
        else:
            self._attr_unique_id = f"{entry.entry_id}_{key}"
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name="WhatsApp")
