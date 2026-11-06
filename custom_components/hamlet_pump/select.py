"""Mode select: auto / run / on / off."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import PumpEntity
from .logic import MODES


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PumpModeSelect(hass.data[DOMAIN][entry.entry_id])])


class PumpModeSelect(PumpEntity, SelectEntity):
    _attr_options = MODES
    _attr_icon = "mdi:pump"

    def __init__(self, controller):
        super().__init__(controller, "mode")

    @property
    def current_option(self):
        return self.controller.mode

    @property
    def extra_state_attributes(self):
        return {"run_until": self.controller.run_until.isoformat() if self.controller.run_until else None}

    async def async_select_option(self, option: str) -> None:
        await self.controller.async_set_mode(option)
