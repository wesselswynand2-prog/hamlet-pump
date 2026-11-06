"""Reset (clears a latched fault) and Run (timed run)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import PumpEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PumpResetButton(c), PumpRunButton(c)])


class PumpResetButton(PumpEntity, ButtonEntity):
    _attr_icon = "mdi:restart-alert"

    def __init__(self, controller):
        super().__init__(controller, "reset")

    async def async_press(self) -> None:
        await self.controller.async_reset()


class PumpRunButton(PumpEntity, ButtonEntity):
    _attr_icon = "mdi:timer-play"

    def __init__(self, controller):
        super().__init__(controller, "run")

    async def async_press(self) -> None:
        await self.controller.async_set_mode("run")
