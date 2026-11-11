"""Constants for Hamlet Pump."""
DOMAIN = "hamlet_pump"
VERSION = "1.1.0"

PANEL_URL_PATH = "hamlet-pump"
PANEL_COMPONENT = "hamlet-pump-panel"
STATIC_URL = "/hamlet_pump_static"

CONF_NAME = "name"
CONF_PUMP_TYPE = "pump_type"
CONF_PUMP_SWITCH = "pump_switch"       # Shelly / Sonoff / contactor relay (optional for a booster the VFD runs itself)
CONF_PUMP_POWER = "pump_power"         # W – Shelly meter or VFD output power
CONF_PUMP_CURRENT = "pump_current"     # A – VFD output current
CONF_PUMP_HZ = "pump_hz"               # Hz – VFD output frequency
CONF_RUNNING = "running_status"        # VFD "running" / pressure-switch contact
CONF_VFD_FAULT = "vfd_fault"           # VFD fault / alarm code
CONF_PRESSURE = "pressure"             # bar
CONF_FLOW = "flow"                     # L/min flow sensor
CONF_WATER_TOTAL = "water_total"       # water meter total (L or m³)
CONF_TANK_LEVEL = "tank_level"         # % (or 0-1); borehole: the tank it fills; booster / irrigation: the supply tank
CONF_TANK_FULL = "tank_full"           # float / probe: ON when full
CONF_TANK_LOW = "tank_low"             # float / probe: ON when low
CONF_FLOATS_INVERT = "floats_invert"   # floats report the other way round
CONF_ZONES = "zones"                   # irrigation valves (switch / valve entities)
CONF_RAIN = "rain_sensor"              # rain / wet sensor (on or > 0 = wet)
CONF_LOAD = "load_sensor"              # panel meter: spare kVA on the supply (or the load in use) – load sharing

TYPE_BOREHOLE = "borehole"
TYPE_BOOSTER = "booster"
TYPE_IRRIGATION = "irrigation"
PUMP_TYPES = [TYPE_BOREHOLE, TYPE_BOOSTER, TYPE_IRRIGATION]

SENSOR_KEYS = [
    CONF_PUMP_POWER, CONF_PUMP_CURRENT, CONF_PUMP_HZ, CONF_RUNNING, CONF_VFD_FAULT, CONF_PRESSURE,
    CONF_FLOW, CONF_WATER_TOTAL, CONF_TANK_LEVEL, CONF_TANK_FULL, CONF_TANK_LOW, CONF_LOAD,
]

SIGNAL_UPDATE = f"{DOMAIN}_update_{{}}"
UPDATE_INTERVAL_S = 5      # protection timers (dry-run etc.) need a short tick
SAMPLE_MINUTES = 5
