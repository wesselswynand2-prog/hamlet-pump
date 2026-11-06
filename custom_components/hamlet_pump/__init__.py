"""Hamlet Pump: borehole / tank filling, pressure pumps and irrigation, with pump protection."""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PANEL_COMPONENT, PANEL_URL_PATH, STATIC_URL, VERSION
from .controller import PumpController
from .logic import MODES

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
CARD_URL = f"{STATIC_URL}/hamlet-pump-card.js?v={VERSION}"
PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    _register_websocket(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.setdefault(DOMAIN, {})
    controller = PumpController(hass, entry)
    data[entry.entry_id] = controller
    await controller.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_panel(hass)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        controller: PumpController = hass.data[DOMAIN].pop(entry.entry_id)
        await controller.async_stop()
        if not _controllers(hass) and hass.data[DOMAIN].pop("_panel", False):
            frontend.async_remove_panel(hass, PANEL_URL_PATH)
        if not _controllers(hass) and hass.data[DOMAIN].pop("_card", False):
            frontend.remove_extra_js_url(hass, CARD_URL)
    return ok


def _controllers(hass: HomeAssistant) -> dict[str, PumpController]:
    return {k: v for k, v in hass.data.get(DOMAIN, {}).items() if isinstance(v, PumpController)}


async def _async_register_panel(hass: HomeAssistant) -> None:
    data = hass.data[DOMAIN]
    if not data.get("_static"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), cache_headers=False)]
        )
        data["_static"] = True
    if not data.get("_card"):
        frontend.add_extra_js_url(hass, CARD_URL)
        data["_card"] = True
    if data.get("_panel"):
        return
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        module_url=f"{STATIC_URL}/hamlet-pump-panel.js?v={VERSION}",
        sidebar_title="Pumps",
        sidebar_icon="mdi:water-pump",
        require_admin=False,
        embed_iframe=False,
    )
    data["_panel"] = True


# ------------------------------------------------------------------ websocket
def _get(hass: HomeAssistant, connection, msg) -> PumpController | None:
    controller = _controllers(hass).get(msg["entry_id"])
    if controller is None:
        connection.send_error(msg["id"], "not_found", "Pump not found")
    return controller


def _register_websocket(hass: HomeAssistant) -> None:
    if hass.data[DOMAIN].get("_ws"):
        return
    hass.data[DOMAIN]["_ws"] = True
    for handler in (ws_list, ws_state, ws_subscribe, ws_set_mode, ws_reset, ws_rain_delay, ws_learn, ws_save_settings):
        websocket_api.async_register_command(hass, handler)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/list"})
@callback
def ws_list(hass, connection, msg):
    connection.send_result(msg["id"], [
        {"entry_id": c.entry.entry_id, "name": c.name, "type": c.pump_type} for c in _controllers(hass).values()
    ])


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/state", vol.Required("entry_id"): str})
@callback
def ws_state(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        connection.send_result(msg["id"], {**controller.snapshot(include_history=True), "is_admin": connection.user.is_admin})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe", vol.Required("entry_id"): str})
@callback
def ws_subscribe(hass, connection, msg):
    controller = _get(hass, connection, msg)
    if controller is None:
        return

    @callback
    def forward() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], controller.snapshot()))

    connection.subscriptions[msg["id"]] = controller.add_listener(forward)
    connection.send_result(msg["id"])
    forward()


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/set_mode",
    vol.Required("entry_id"): str,
    vol.Required("mode"): vol.In(MODES),
    vol.Optional("minutes"): vol.All(vol.Coerce(float), vol.Range(min=1, max=720)),
    vol.Optional("zone"): vol.Coerce(int),
})
@websocket_api.async_response
async def ws_set_mode(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        try:
            await controller.async_set_mode(msg["mode"], msg.get("minutes"), msg.get("zone"))
        except ValueError as err:
            connection.send_error(msg["id"], "invalid", str(err))
            return
        connection.send_result(msg["id"], controller.snapshot())


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/reset", vol.Required("entry_id"): str})
@websocket_api.async_response
async def ws_reset(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        await controller.async_reset()
        connection.send_result(msg["id"], controller.snapshot())


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/rain_delay",
    vol.Required("entry_id"): str,
    vol.Required("days"): vol.All(vol.Coerce(float), vol.Range(min=0, max=14)),
})
@websocket_api.async_response
async def ws_rain_delay(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        await controller.async_rain_delay(msg["days"])
        connection.send_result(msg["id"], controller.snapshot())


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/learn", vol.Required("entry_id"): str})
@websocket_api.async_response
async def ws_learn(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        try:
            learned = await controller.async_learn()
        except ValueError as err:
            connection.send_error(msg["id"], "invalid", str(err))
            return
        connection.send_result(msg["id"], {"learned": learned, **controller.snapshot()})


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/save_settings",
    vol.Required("entry_id"): str,
    vol.Required("settings"): dict,
})
@websocket_api.async_response
async def ws_save_settings(hass, connection, msg):
    if controller := _get(hass, connection, msg):
        try:
            await controller.async_update_settings(msg["settings"], connection.user.is_admin)
        except (ValueError, KeyError, TypeError) as err:
            connection.send_error(msg["id"], "invalid", str(err))
            return
        connection.send_result(msg["id"], controller.snapshot())
