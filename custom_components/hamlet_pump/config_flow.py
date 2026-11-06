"""Config flow: the installer picks the kind of installation and maps the client's own entities."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_FLOATS_INVERT,
    CONF_FLOW,
    CONF_NAME,
    CONF_PRESSURE,
    CONF_PUMP_CURRENT,
    CONF_PUMP_HZ,
    CONF_PUMP_POWER,
    CONF_PUMP_SWITCH,
    CONF_PUMP_TYPE,
    CONF_RAIN,
    CONF_RUNNING,
    CONF_TANK_FULL,
    CONF_TANK_LEVEL,
    CONF_TANK_LOW,
    CONF_VFD_FAULT,
    CONF_WATER_TOTAL,
    CONF_ZONES,
    DOMAIN,
    PUMP_TYPES,
    SENSOR_KEYS,
    TYPE_BOOSTER,
    TYPE_BOREHOLE,
    TYPE_IRRIGATION,
)

ON_OFF = ["binary_sensor", "sensor", "switch", "input_boolean"]
SWITCHES = ["switch", "input_boolean", "light", "valve"]
DEFAULT_NAMES = {TYPE_BOREHOLE: "Borehole", TYPE_BOOSTER: "Pressure pump", TYPE_IRRIGATION: "Irrigation"}


def _ent(domains: list[str], multiple: bool = False) -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain=domains, multiple=multiple))


def _num() -> selector.EntitySelector:
    # device_class deliberately not enforced: Modbus / template sensors often lack one
    return _ent(["sensor", "input_number", "number"])


def _pump_schema() -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_PUMP_TYPE, default=TYPE_BOREHOLE): selector.SelectSelector(
            selector.SelectSelectorConfig(options=PUMP_TYPES, translation_key="pump_type", mode=selector.SelectSelectorMode.LIST)
        ),
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_PUMP_SWITCH): _ent(["switch", "input_boolean", "light"]),
    })


def _sensor_schema() -> vol.Schema:
    return vol.Schema({
        vol.Optional(CONF_PUMP_POWER): _num(),
        vol.Optional(CONF_PUMP_CURRENT): _num(),
        vol.Optional(CONF_PUMP_HZ): _num(),
        vol.Optional(CONF_RUNNING): _ent(ON_OFF),
        vol.Optional(CONF_VFD_FAULT): _ent(ON_OFF),
        vol.Optional(CONF_PRESSURE): _num(),
        vol.Optional(CONF_FLOW): _num(),
        vol.Optional(CONF_WATER_TOTAL): _num(),
        vol.Optional(CONF_TANK_LEVEL): _num(),
        vol.Optional(CONF_TANK_FULL): _ent(ON_OFF),
        vol.Optional(CONF_TANK_LOW): _ent(ON_OFF),
        vol.Required(CONF_FLOATS_INVERT, default=False): selector.BooleanSelector(),
    })


def _zones_schema() -> vol.Schema:
    return vol.Schema({
        vol.Optional(CONF_ZONES): _ent(SWITCHES, multiple=True),
        vol.Optional(CONF_RAIN): _ent(ON_OFF),
    })


def _pump_errors(data: dict) -> dict:
    if data.get(CONF_PUMP_TYPE) == TYPE_BOREHOLE and not data.get(CONF_PUMP_SWITCH):
        return {CONF_PUMP_SWITCH: "switch_required"}
    return {}


def _zone_errors(data: dict, full: dict) -> dict:
    if not data.get(CONF_ZONES) and not full.get(CONF_PUMP_SWITCH):
        return {"base": "zones_or_switch"}
    return {}


class HamletPumpConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict = {}
        if user_input is not None:
            errors = _pump_errors(user_input)
            if not errors:
                user_input[CONF_NAME] = (user_input.get(CONF_NAME) or "").strip() or DEFAULT_NAMES[user_input[CONF_PUMP_TYPE]]
                if user_input.get(CONF_PUMP_SWITCH):
                    await self.async_set_unique_id(user_input[CONF_PUMP_SWITCH])
                    self._abort_if_unique_id_configured()
                self._data.update(user_input)
                return await self.async_step_sensors()
        schema = _pump_schema()
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_sensors(self, user_input: dict | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            if self._data[CONF_PUMP_TYPE] == TYPE_IRRIGATION:
                return await self.async_step_zones()
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return self.async_show_form(step_id="sensors", data_schema=_sensor_schema(),
                                    description_placeholders={"type": self._data[CONF_PUMP_TYPE]})

    async def async_step_zones(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict = {}
        if user_input is not None:
            errors = _zone_errors(user_input, self._data)
            if not errors:
                self._data.update(user_input)
                return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return self.async_show_form(step_id="zones", data_schema=_zones_schema(), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HamletPumpOptionsFlow()


class HamletPumpOptionsFlow(OptionsFlow):
    """Re-map entities later (e.g. after replacing a relay or adding a level sensor)."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    @property
    def _current(self) -> dict:
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict = {}
        if user_input is not None:
            errors = _pump_errors(user_input)
            if not errors:
                user_input[CONF_NAME] = (user_input.get(CONF_NAME) or "").strip() or self._current.get(CONF_NAME) or DEFAULT_NAMES[user_input[CONF_PUMP_TYPE]]
                self._data.update({CONF_PUMP_SWITCH: None})
                self._data.update(user_input)
                return await self.async_step_sensors()
        schema = self.add_suggested_values_to_schema(_pump_schema(), user_input or self._current)
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def async_step_sensors(self, user_input: dict | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update({k: None for k in SENSOR_KEYS})
            self._data.update(user_input)
            if self._data[CONF_PUMP_TYPE] == TYPE_IRRIGATION:
                return await self.async_step_zones()
            return self.async_create_entry(title="", data=self._data)
        schema = self.add_suggested_values_to_schema(_sensor_schema(), self._current)
        return self.async_show_form(step_id="sensors", data_schema=schema,
                                    description_placeholders={"type": self._data[CONF_PUMP_TYPE]})

    async def async_step_zones(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict = {}
        if user_input is not None:
            errors = _zone_errors(user_input, self._data)
            if not errors:
                self._data.update({CONF_ZONES: None, CONF_RAIN: None})
                self._data.update(user_input)
                return self.async_create_entry(title="", data=self._data)
        schema = self.add_suggested_values_to_schema(_zones_schema(), user_input or self._current)
        return self.async_show_form(step_id="zones", data_schema=schema, errors=errors)
