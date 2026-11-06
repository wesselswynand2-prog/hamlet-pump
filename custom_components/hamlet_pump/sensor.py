"""Status, power, water and run-time sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTime, UnitOfVolume
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import PumpEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        PumpStatusSensor(c), PumpPowerSensor(c), PumpFlowSensor(c),
        DailySensor(c, "water_today", "litres", SensorDeviceClass.WATER, UnitOfVolume.LITERS, "mdi:water", 0),
        DailySensor(c, "energy_today", "kwh", SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, None, 2),
        DailySensor(c, "run_time_today", "run_s", SensorDeviceClass.DURATION, UnitOfTime.MINUTES, "mdi:timer-outline", 0),
        DailySensor(c, "starts_today", "starts", None, None, "mdi:counter", 0),
    ])


class PumpStatusSensor(PumpEntity, SensorEntity):
    _attr_icon = "mdi:pump"

    def __init__(self, controller):
        super().__init__(controller, "status")

    @property
    def native_value(self):
        d = self.controller.decision
        return d.status if d else None

    @property
    def extra_state_attributes(self):
        d = self.controller.decision
        if d is None:
            return {}
        return {"reason": d.reason, "pump_on": d.on, "source": d.source, "zone": None if d.zone is None else d.zone + 1,
                "program": d.program, "type": self.controller.pump_type}


class PumpPowerSensor(PumpEntity, SensorEntity):
    """The meter, or the pump rating while it runs (speed-scaled for a VFD) – so the Energy dashboard can count it."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, controller):
        super().__init__(controller, "pump_power")

    @property
    def native_value(self):
        v = self.controller.live.get("power_est")
        return None if v is None else round(v)

    @property
    def extra_state_attributes(self):
        return {"estimated": self.controller.live.get("power") is None}


class PumpFlowSensor(PumpEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "L/min"
    _attr_icon = "mdi:waves-arrow-right"

    def __init__(self, controller):
        super().__init__(controller, "flow")

    @property
    def native_value(self):
        v = self.controller.live.get("flow_est")
        return None if v is None else round(v, 1)

    @property
    def extra_state_attributes(self):
        return {"source": self.controller.water_source()}


class DailySensor(PumpEntity, SensorEntity):
    def __init__(self, controller, key, field, device_class, unit, icon, precision):
        super().__init__(controller, key)
        self.field = field
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_suggested_display_precision = precision
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING if device_class in (SensorDeviceClass.WATER, SensorDeviceClass.ENERGY) else SensorStateClass.MEASUREMENT
        if icon:
            self._attr_icon = icon

    @property
    def native_value(self):
        today = self.controller.daily.get(dt_util.now().date().isoformat(), {})
        v = today.get(self.field, 0)
        if self.field == "run_s":
            return round(v / 60, 1)
        if self.field == "starts":
            return int(v)
        return round(v, 3 if self.field == "kwh" else 0)
