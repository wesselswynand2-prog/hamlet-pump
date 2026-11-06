"""Shared entity base."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_UPDATE, VERSION
from .controller import PumpController

MODELS = {"borehole": "Borehole & Tank Controller", "booster": "Pressure Pump Monitor", "irrigation": "Irrigation Controller"}


class PumpEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: PumpController, key: str) -> None:
        self.controller = controller
        self._attr_unique_id = f"{controller.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.entry.entry_id)},
            name=controller.name,
            manufacturer="Hamlet Elektries",
            model=MODELS.get(controller.pump_type, "Pump Controller"),
            sw_version=VERSION,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE.format(self.controller.entry.entry_id), self.async_write_ha_state
            )
        )
