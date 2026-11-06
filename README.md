# Hamlet Pump

Pump control and protection for Home Assistant, for three kinds of installation:

| Installation | What the app does |
|---|---|
| **Borehole / pump filling a tank** (JoJo) | Fills the tank by level sensor, floats or a timer. Protects against dry-running, overload and a tank that isn't filling (dry borehole, burst pipe, closed valve). Rests the borehole after long runs. Optional pumping hours. |
| **Pressure / booster pump** (house supply) | The VFD or pressure switch runs the pump; the app enables it and watches for dry-running, no pressure, leaks (running non-stop), short-cycling (pressure vessel), a low supply tank and VFD faults. Works monitor-only if there's no relay. |
| **Irrigation pump** | Watering programs over zones (valves), one zone at a time. Opens the valve before starting the pump. Rain sensor skip, rain delay, manual zone runs, low supply-tank protection. |

Installs as a **Pumps** page in the Home Assistant sidebar (tabs when there are several pumps), a dashboard card, and normal entities for automations. Shows water used today and per day, run time, starts and energy.

## Install on a client's Home Assistant

**Option A – HACS**
1. HACS → ⋮ → Custom repositories → add `https://github.com/wesselswynand2-prog/hamlet-pump`, type *Integration*.
2. Search **Hamlet Pump** → Download, restart Home Assistant.

**Option B – upload the zip + one terminal command** (same as Hamlet Geyser)
1. Upload `hamlet-pump.zip` into the Home Assistant config folder.
2. In the **Terminal & SSH** add-on:
   - First time: `cd /config 2>/dev/null || cd /homeassistant; mkdir -p /tmp/hp && unzip -oq "$(ls -t hamlet-pump*.zip | head -1)" -d /tmp/hp && sh /tmp/hp/hamlet-pump/hamlet-update.sh`
   - Updates: `sh /config/hamlet-update.sh` (the same script updates every Hamlet app)

**Option C – manual copy:** copy `custom_components/hamlet_pump` into `/config/custom_components/` and restart.

Then: **Settings → Devices & services → Add integration → Hamlet Pump**, pick the installation type and map the entities. Add the integration again for a second pump.

## Mapping cheat-sheet

Everything except the pump switch is optional – map what the installation has.

| Field | Typical entity |
|---|---|
| Pump switch | Shelly Pro 1PM / Plus 1PM, Sonoff, or the relay driving the contactor coil. **Required for a borehole.** Leave empty for a VFD booster you only want to monitor. |
| Pump power (W) | Shelly power sensor, or the VFD's output power (Modbus) |
| Pump current (A) | VFD output current |
| VFD frequency (Hz) | VFD output frequency – above 0 Hz means running; also scales the water/energy estimate |
| Pump running signal | VFD "running" status, or a contact on the pressure switch |
| VFD fault / alarm | VFD fault code (0 = OK) or alarm binary sensor |
| Water pressure | Pressure transducer or VFD feedback (bar, kPa, psi converted) |
| Flow | Flow sensor (L/min, L/h, m³/h converted) |
| Water meter total | Pulse water meter counting up (L or m³) – most accurate water figure |
| Tank level (%) | Ultrasonic / pressure level sensor (0–1 is read as a fraction). Borehole: the tank being filled. Booster / irrigation: the supply tank. |
| Tank FULL / LOW float | Float switch or probe on a Shelly input. Tick *Floats report the other way round* if needed. |
| Irrigation valves | Valve relays in watering order (switch or valve entities) |
| Rain sensor | ON / wet = skip watering |

**How "running" is worked out:** running signal → else Hz > 0 → else power above 20 W (pressure-switch pumps on an always-on Shelly) → else the relay state.

**Water used:** water meter → else flow sensor → else estimated from run time × *Pump flow at full speed* (scaled by Hz on a VFD). The page says which.

## Set up protection (Installer settings)

1. Start the pump and let it run normally (water flowing).
2. Pumps page → Installer settings → **Learn from this run**. It sets dry-run at 60 % and overload at 140 % of the normal power / current.
3. Check the other limits for the installation type.

| Protection | Default | What happens |
|---|---|---|
| Dry-run (power or current too low) | off until learned / set; must last 15 s, ignored for 10 s after a start | Stops, waits 30 min, tries again. After 3 tries in a row: **locked out** until Reset |
| Overload (power or current too high) | off until learned / set; 5 s | Locked out |
| Borehole: tank must rise 1 % | within 20 min of pumping | Locked out – dry borehole, leaking pipe or closed valve |
| Borehole: rest after long run | 180 min, rest 30 min | Pauses, then carries on filling |
| Booster: no pressure while running | off (set e.g. 1 bar), 60 s | Stops, waits, retries like dry-run |
| Booster: running non-stop | 30 min | Warning (or stop, if set) – leak or tap left open |
| Booster: short-cycling | more than 20 starts / hour | Warning – check the pressure vessel's air charge, dripping tap |
| Supply tank low (booster / irrigation) | stop below 10 %, restart at 20 % | Stops until the tank recovers |
| Restart delay | 30 s | A restart waits this long after the last switch. **Stopping is always immediate.** |

A full tank always stops a borehole pump, even in *On* or *Run* mode. Protection is active in every mode except *Off*.

Alerts appear in the Pumps page, as Home Assistant notifications and, if set, on a phone via *Send alerts to* (e.g. `notify.mobile_app_wynand`).

## Modes

**Auto** (normal), **Run** (timed 10 min – 2 h, then back to Auto; for irrigation it waters one zone), **On** (until set back, protection still active), **Off**.
The app owns the relay: if someone switches the Shelly by hand, Auto puts it back – use the modes instead.

Clients (non-admin users) can change fill levels, pumping hours, timers, watering programs and rain delay. Protection and ratings are admin-only.

## Dashboard card

Loaded automatically. Edit dashboard → **Add card** → **Hamlet Pump**, or:

```yaml
type: custom:hamlet-pump-card
pump: Borehole      # optional – name of the pump; default is the first one
show_today: true    # water / run time / starts today
```

## Entities (per pump)

`select.<name>_mode`, `button.<name>_reset_fault`, `button.<name>_run_now`, `sensor.<name>_status` (reason in attributes), `binary_sensor.<name>_running`, `binary_sensor.<name>_fault`, `sensor.<name>_pump_power` (measured or estimated – usable in the Energy dashboard), `sensor.<name>_flow`, and today's `water_today` (L), `energy_today` (kWh), `run_time_today` (min), `starts_today`.

## Tests

```
pip install -r requirements_test.txt
pytest
```
