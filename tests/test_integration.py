"""End-to-end tests inside a real Home Assistant instance (pytest-homeassistant-custom-component)."""
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_mock_service

DOMAIN = "hamlet_pump"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _base(hass):
    for mod in ("http", "frontend"):
        assert await async_setup_component(hass, mod, {})


async def _flow(hass, user: dict, sensors: dict, zones: dict | None = None):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user)
    assert result.get("step_id") == "sensors", result.get("errors")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], sensors)
    if zones is not None:
        assert result["step_id"] == "zones"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], zones)
    assert result["type"] == "create_entry", result
    await hass.async_block_till_done()
    return result["result"]


async def test_borehole_flow(hass: HomeAssistant, hass_ws_client):
    await _base(hass)
    on = async_mock_service(hass, "homeassistant", "turn_on")
    off = async_mock_service(hass, "homeassistant", "turn_off")
    hass.states.async_set("switch.borehole", "off")
    hass.states.async_set("sensor.borehole_power", "0", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.jojo_level", "0.3", {})   # a 0-1 fraction -> 30 %

    # a borehole needs a switch
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"pump_type": "borehole"})
    assert result["errors"] == {"pump_switch": "switch_required"}

    entry = await _flow(hass, {"pump_type": "borehole", "name": "Borehole", "pump_switch": "switch.borehole"},
                        {"pump_power": "sensor.borehole_power", "tank_level": "sensor.jojo_level"})

    # 30 % < 40 % start -> fills
    assert on and on[-1].data["entity_id"] == "switch.borehole"
    assert hass.states.get("sensor.borehole_status").state == "Filling"
    assert hass.states.get("select.borehole_mode").state == "auto"
    assert hass.states.get("binary_sensor.borehole_fault").state == "off"
    assert "hamlet-pump" in hass.data["frontend_panels"]
    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
    assert any("hamlet-pump-card.js" in u for u in hass.data[DATA_EXTRA_MODULE_URL].urls)

    hass.states.async_set("switch.borehole", "on")
    hass.states.async_set("sensor.borehole_power", "950", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.borehole_running").state == "on"
    assert hass.states.get("sensor.borehole_pump_power").state == "950"

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/list"})
    msg = await client.receive_json()
    assert msg["result"] == [{"entry_id": entry.entry_id, "name": "Borehole", "type": "borehole"}]

    await client.send_json({"id": 2, "type": f"{DOMAIN}/state", "entry_id": entry.entry_id})
    snap = (await client.receive_json())["result"]
    assert snap["live"]["level"] == 30 and snap["features"]["level"] and snap["is_admin"]
    assert len(snap["days"]) == 14

    # learn dry-run / overload from a normal run
    await client.send_json({"id": 3, "type": f"{DOMAIN}/learn", "entry_id": entry.entry_id})
    msg = await client.receive_json()
    assert msg["success"], msg
    assert msg["result"]["learned"] == {"dry_run_w": 570, "overload_w": 1330}

    # full -> stops
    hass.states.async_set("sensor.jojo_level", "96", {"unit_of_measurement": "%"})
    await hass.async_block_till_done()
    assert off and off[-1].data["entity_id"] == "switch.borehole"
    assert hass.states.get("sensor.borehole_status").state == "Tank full"

    # settings: client may change levels but not protection
    await client.send_json({"id": 4, "type": f"{DOMAIN}/save_settings", "entry_id": entry.entry_id,
                            "settings": {"start_level": 50, "stop_level": 90, "notify_service": "notify.mobile_app_x"}})
    msg = await client.receive_json()
    assert msg["success"], msg
    assert msg["result"]["settings"]["start_level"] == 50

    await client.send_json({"id": 5, "type": f"{DOMAIN}/save_settings", "entry_id": entry.entry_id,
                            "settings": {"start_level": 95}})
    msg = await client.receive_json()
    assert not msg["success"]

    # a latched fault and reset through the button entity
    ctrl = hass.data[DOMAIN][entry.entry_id]
    ctrl.state.fault = "Overload: test"
    await ctrl.async_evaluate()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.borehole_status").state == "Fault"
    assert hass.states.get("binary_sensor.borehole_fault").state == "on"
    await hass.services.async_call("button", "press", {"entity_id": "button.borehole_reset_fault"}, blocking=True)
    await hass.async_block_till_done()
    assert ctrl.state.fault is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert "hamlet-pump" not in hass.data["frontend_panels"]


async def test_booster_monitor_only(hass: HomeAssistant):
    await _base(hass)
    hass.states.async_set("sensor.vfd_hz", "0", {"unit_of_measurement": "Hz"})
    hass.states.async_set("sensor.vfd_pressure", "320", {"unit_of_measurement": "kPa"})
    hass.states.async_set("sensor.vfd_fault", "0")
    await _flow(hass, {"pump_type": "booster", "name": "House pump"},
                {"pump_hz": "sensor.vfd_hz", "pressure": "sensor.vfd_pressure", "vfd_fault": "sensor.vfd_fault"})
    ctrl = next(v for k, v in hass.data[DOMAIN].items() if not k.startswith("_"))
    assert hass.states.get("sensor.house_pump_status").state == "Ready"
    assert ctrl.live["pressure"] == pytest.approx(3.2)

    hass.states.async_set("sensor.vfd_hz", "45", {"unit_of_measurement": "Hz"})
    await hass.async_block_till_done()
    assert hass.states.get("sensor.house_pump_status").state == "Pumping"
    # estimated: 40 L/min at 50 Hz -> 36 L/min at 45 Hz
    assert float(hass.states.get("sensor.house_pump_flow").state) == pytest.approx(36)

    hass.states.async_set("sensor.vfd_fault", "12")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.house_pump_status").state == "VFD fault"


async def test_irrigation_valves_then_pump(hass: HomeAssistant, hass_ws_client):
    await _base(hass)
    on = async_mock_service(hass, "homeassistant", "turn_on")
    async_mock_service(hass, "homeassistant", "turn_off")
    for e in ("switch.garden_pump", "switch.zone_front", "switch.zone_back"):
        hass.states.async_set(e, "off")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"pump_type": "irrigation"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "zones_or_switch"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"zones": ["switch.zone_front", "switch.zone_back"]})
    assert result["type"] == "create_entry"
    entry = result["result"]
    assert entry.title == "Irrigation"
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/set_mode", "entry_id": entry.entry_id, "mode": "run", "minutes": 5, "zone": 1})
    msg = await client.receive_json()
    assert msg["success"], msg
    await hass.async_block_till_done()
    assert any(c.data["entity_id"] == "switch.zone_back" for c in on)
    assert hass.states.get("sensor.irrigation_status").state == "Running"

    await client.send_json({"id": 2, "type": f"{DOMAIN}/rain_delay", "entry_id": entry.entry_id, "days": 2})
    msg = await client.receive_json()
    assert msg["success"] and msg["result"]["rain_delay_until"]
