"""Running and fault."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import PumpEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PumpRunningSensor(c), PumpFaultSensor(c)])


class PumpRunningSensor(PumpEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:pump"

    def __init__(self, controller):
        super().__init__(controller, "running")

    @property
    def is_on(self):
        return self.controller.live.get("running")


class PumpFaultSensor(PumpEntity, BinarySensorEntity):
    """On while the pump is locked out, resting after a trip, or the VFD reports a fault."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, controller):
        super().__init__(controller, "fault")

    @property
    def is_on(self):
        d = self.controller.decision
        return bool(self.controller.state.fault) or (d is not None and d.status in ("Fault", "Resting", "VFD fault", "Tank low"))

    @property
    def extra_state_attributes(self):
        d = self.controller.decision
        return {"latched": bool(self.controller.state.fault), "reason": d.reason if d and self.is_on else None}
