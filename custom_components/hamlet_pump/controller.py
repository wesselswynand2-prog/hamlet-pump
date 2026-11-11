"""Runtime controller: reads sensors, decides, switches the pump and valves, keeps history and water use."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import logic
from .const import (
    CONF_FLOATS_INVERT,
    CONF_FLOW,
    CONF_NAME,
    CONF_PRESSURE,
    CONF_LOAD,
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
    SAMPLE_MINUTES,
    SENSOR_KEYS,
    SIGNAL_UPDATE,
    TYPE_BOREHOLE,
    TYPE_IRRIGATION,
    UPDATE_INTERVAL_S,
)

_LOGGER = logging.getLogger(__name__)
STORE_VERSION = 1
BAD_STATES = (STATE_UNAVAILABLE, STATE_UNKNOWN, None, "", "none")
TRUE_WORDS = {"on", "true", "1", "yes", "running", "run", "active", "pumping", "wet", "rain", "raining", "open", "full", "low", "detected"}
OK_WORDS = {"0", "ok", "none", "no fault", "no error", "normal", "off", "false", "no alarm", "ready", "running", "stopped", "idle", ""}


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


class PumpController:
    """One pump installation."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.settings: dict = dict(logic.DEFAULT_SETTINGS)
        self.mode = "auto"
        self.run_until: datetime | None = None
        self.manual_zone: int | None = None
        self.rain_delay_until: datetime | None = None
        self.state = logic.State()
        self.decision: logic.Decision | None = None
        self.live: dict[str, Any] = {}
        self.history: dict[str, list] = {}   # day -> [[minute, run_frac, level, pressure, power, litres], ...]
        self.daily: dict[str, dict[str, float]] = {}   # day -> {run_s, starts, litres, kwh}
        self.events: list[dict] = []         # recent faults / alerts for the page
        self._bucket: dict[str, Any] = {}
        self._last_tick: datetime | None = None
        self._last_total: float | None = None
        self._last_command: datetime | None = None
        self._zone_since: tuple[int, datetime] | None = None
        self._unsubs: list[CALLBACK_TYPE] = []
        self._listeners: list[Callable[[], None]] = []
        self._busy = False
        self._cmd_error: str | None = None

    # ------------------------------------------------------------------ config
    @property
    def conf(self) -> dict:
        return {**self.entry.data, **self.entry.options}

    @property
    def name(self) -> str:
        return self.conf.get(CONF_NAME, "Pump")

    @property
    def pump_type(self) -> str:
        return self.conf.get(CONF_PUMP_TYPE) or TYPE_BOREHOLE

    @property
    def zones(self) -> list[str]:
        return _as_list(self.conf.get(CONF_ZONES)) if self.pump_type == TYPE_IRRIGATION else []

    def _watched(self) -> list[str]:
        c = self.conf
        ids = _as_list(c.get(CONF_PUMP_SWITCH)) + _as_list(c.get(CONF_RAIN)) + self.zones
        for key in SENSOR_KEYS:
            ids += _as_list(c.get(key))
        return ids

    # --------------------------------------------------------------- lifecycle
    async def async_start(self) -> None:
        data = await self.store.async_load() or {}
        self.settings = {**logic.DEFAULT_SETTINGS, **data.get("settings", {})}
        self.mode = data.get("mode", "auto")
        self.run_until = dt_util.parse_datetime(data["run_until"]) if data.get("run_until") else None
        self.manual_zone = data.get("manual_zone")
        self.rain_delay_until = dt_util.parse_datetime(data["rain_delay_until"]) if data.get("rain_delay_until") else None
        st = data.get("state", {})
        self.state.fault = st.get("fault")
        self.state.retries = int(st.get("retries", 0))
        self.state.shed = bool(st.get("shed", False))     # still load-shed after a restart
        self.state.resume = bool(st.get("resume", False))
        if st.get("rest_until"):
            self.state.rest_until = dt_util.parse_datetime(st["rest_until"])
            self.state.rest_why = st.get("rest_why", "Resting")
        self.history = data.get("history", {})
        self.daily = data.get("daily", {})
        self.events = data.get("events", [])
        self._prune()
        self._unsubs.append(async_track_state_change_event(self.hass, self._watched(), self._on_state_change))
        self._unsubs.append(async_track_time_interval(self.hass, self._on_tick, timedelta(seconds=UPDATE_INTERVAL_S)))
        await self.async_evaluate()

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._flush_bucket()
        await self.store.async_save(self._store_data())

    def _store_data(self) -> dict:
        st = self.state
        return {
            "settings": self.settings,
            "mode": self.mode,
            "run_until": self.run_until.isoformat() if self.run_until else None,
            "manual_zone": self.manual_zone,
            "rain_delay_until": self.rain_delay_until.isoformat() if self.rain_delay_until else None,
            "state": {"fault": st.fault, "retries": st.retries, "rest_why": st.rest_why, "shed": st.shed, "resume": st.resume,
                      "rest_until": st.rest_until.isoformat() if st.rest_until else None},
            "history": self.history,
            "daily": self.daily,
            "events": self.events[-30:],
        }

    def _save(self, delay: float = 2) -> None:
        self.store.async_delay_save(self._store_data, delay)

    def _prune(self) -> None:
        today = dt_util.now().date()
        keep = {(today - timedelta(days=n)).isoformat() for n in range(2)}
        self.history = {k: v for k, v in self.history.items() if k in keep}
        keep31 = {(today - timedelta(days=n)).isoformat() for n in range(31)}
        self.daily = {k: v for k, v in self.daily.items() if k in keep31}

    # -------------------------------------------------------------- listeners
    @callback
    def add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)

        def remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return remove

    def _notify(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(self.entry.entry_id))
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Listener failed")

    async def _on_state_change(self, event: Event) -> None:
        await self.async_evaluate()

    async def _on_tick(self, now: datetime) -> None:
        self._sample()
        await self.async_evaluate()

    # ------------------------------------------------------------------ reading
    def _state(self, entity_id: str | None):
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return None if st is None or st.state in BAD_STATES else st

    def _float(self, entity_id: str | None, kind: str = "") -> float | None:
        st = self._state(entity_id)
        if st is None:
            return None
        try:
            value = float(st.state)
        except (TypeError, ValueError):
            return None
        unit = (st.attributes.get("unit_of_measurement") or "").strip()
        if kind == "power" and unit == "kW":
            value *= 1000
        elif kind == "pressure":
            value = {"kPa": value / 100, "psi": value * 0.0689476, "Pa": value / 100000, "mbar": value / 1000, "MPa": value * 10}.get(unit, value)
        elif kind == "flow":
            value = {"m³/h": value * 1000 / 60, "L/h": value / 60, "L/s": value * 60, "gal/min": value * 3.785}.get(unit, value)
        elif kind == "level" and unit != "%" and 0 <= value <= 1 and "level" not in unit:
            value *= 100   # 0-1 fraction
        elif kind == "water":
            value = {"m³": value * 1000, "kL": value * 1000, "gal": value * 3.785}.get(unit, value)
        return value

    def _bool(self, entity_id: str | None) -> bool | None:
        st = self._state(entity_id)
        if st is None:
            return None
        raw = str(st.state).strip().lower()
        try:
            return float(raw) > 0
        except ValueError:
            return raw in TRUE_WORDS

    def _float_switch(self, key: str) -> bool | None:
        v = self._bool(self.conf.get(key))
        if v is not None and self.conf.get(CONF_FLOATS_INVERT):
            v = not v
        return v

    def _vfd_fault(self) -> str | None:
        st = self._state(self.conf.get(CONF_VFD_FAULT))
        if st is None:
            return None
        raw = str(st.state).strip()
        try:
            return None if float(raw) == 0 else f"code {raw}"
        except ValueError:
            pass
        if st.entity_id.startswith("binary_sensor."):
            return "alarm" if raw.lower() == "on" else None
        return None if raw.lower() in OK_WORDS else raw

    def read_inputs(self) -> logic.Inputs:
        c = self.conf
        s = self.settings
        sw = self._state(c.get(CONF_PUMP_SWITCH))
        is_on = None if sw is None else sw.state == STATE_ON
        power = self._float(c.get(CONF_PUMP_POWER), "power")
        hz = self._float(c.get(CONF_PUMP_HZ))
        running = self._bool(c.get(CONF_RUNNING))
        if running is None and hz is not None:
            running = hz > 0.5
        if running is None and power is not None:
            running = bool(is_on is not False) and power > float(s["running_above_w"])
        if running is None:
            running = is_on
        return logic.Inputs(
            now=dt_util.now(),
            pump_type=self.pump_type,
            mode=self.mode,
            run_until=self.run_until,
            manual_zone=self.manual_zone,
            has_switch=bool(c.get(CONF_PUMP_SWITCH)),
            is_on=is_on,
            running=running,
            last_change=self._last_command,
            power=power,
            amps=self._float(c.get(CONF_PUMP_CURRENT)),
            hz=hz,
            pressure=self._float(c.get(CONF_PRESSURE), "pressure"),
            flow=self._float(c.get(CONF_FLOW), "flow"),
            level=self._float(c.get(CONF_TANK_LEVEL), "level"),
            tank_full=self._float_switch(CONF_TANK_FULL),
            tank_low=self._float_switch(CONF_TANK_LOW),
            vfd_fault=self._vfd_fault(),
            rain=self._bool(c.get(CONF_RAIN)),
            rain_delay_until=self.rain_delay_until,
            zone_count=len(self.zones),
            spare_kva=self._spare_kva(),
            load_sensor=bool(c.get(CONF_LOAD)),
        )

    def _spare_kva(self) -> float | None:
        """Spare capacity on the supply in kVA, from the panel meter (load sharing)."""
        st = self._state(self.conf.get(CONF_LOAD))
        if st is None:
            return None
        try:
            v = float(st.state)
        except (TypeError, ValueError):
            return None
        unit = (st.attributes.get("unit_of_measurement") or "").strip()
        if unit in ("W", "VA"):
            v /= 1000
        elif unit in ("MW", "MVA"):
            v *= 1000
        if self.settings.get("load_mode") == "used":
            size = float(self.settings.get("supply_kva") or 0)
            return round(size - v, 2) if size > 0 else None
        return round(v, 2)

    # -------------------------------------------------------------- decision
    async def async_evaluate(self) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            await self._evaluate()
        finally:
            self._busy = False

    async def _evaluate(self) -> None:
        inp = self.read_inputs()
        prev_fault, prev_rest, prev_shed = self.state.fault, self.state.rest_until, self.state.shed
        d = logic.decide(inp, self.settings, self.state)
        if self.state.shed != prev_shed:   # load sharing: log it on the page, no notification (it's normal)
            spare = "–" if inp.spare_kva is None else f"{inp.spare_kva:.1f} kVA"
            self.events.append({"t": inp.now.isoformat(), "kind": "load",
                                "msg": f"Stopped for load sharing – {spare} spare" if self.state.shed else f"Load back down – {spare} spare, pump released"})
            self.events = self.events[-30:]
            self._save()
        if d.run_expired and self.mode == "run":
            self.mode, self.run_until, self.manual_zone = "auto", None, None
            self._save()
        if self.state.fault != prev_fault or self.state.rest_until != prev_rest:
            self._save()
        for key, msg in d.alerts:
            await self._alert(key, msg, d.status)

        switch_id = self.conf.get(CONF_PUMP_SWITCH)
        want_pump = d.on
        # irrigation: valve first, then the pump; open the new zone before closing the old one
        if self.zones:
            want_pump = await self._drive_valves(d, inp)
        self._cmd_error = None
        if switch_id and inp.is_on is not None and want_pump != inp.is_on and not d.held:
            if not (inp.is_on is False and want_pump and d.status == "VFD fault"):
                await self._switch(switch_id, want_pump, d.reason)
        if self.zones and not d.on:
            await self._close_valves(keep=None)
        if switch_id and inp.is_on is None:
            d.status, d.reason = "Offline", f"Can't reach the pump switch ({switch_id}). Check the relay has power and Wi-Fi."

        self.decision = d
        self.live = {
            "is_on": inp.is_on, "running": inp.running, "power": inp.power, "amps": inp.amps, "hz": inp.hz,
            "pressure": inp.pressure, "flow": inp.flow, "level": inp.level, "tank_full": inp.tank_full,
            "tank_low": inp.tank_low, "vfd_fault": inp.vfd_fault, "rain": inp.rain,
            "zones": [self._bool(z) for z in self.zones],
            "power_est": self._power_estimate(inp),
            "flow_est": self._flow_estimate(inp),
            "run_for_s": (inp.now - self.state.run_since).total_seconds() if self.state.run_since else None,
            "starts_hour": len(self.state.starts),
            "retries": self.state.retries,
            "cmd_error": self._cmd_error,
            "spare_kva": inp.spare_kva,
            "shed": self.state.shed,
        }
        self._notify()

    async def _switch(self, entity_id: str, on: bool, why: str) -> None:
        domain = entity_id.split(".", 1)[0]
        if domain == "valve":
            service, svc_domain = ("open_valve" if on else "close_valve"), "valve"
        else:
            service, svc_domain = ("turn_on" if on else "turn_off"), "homeassistant"
        _LOGGER.debug("%s: %s %s (%s)", self.name, service, entity_id, why)
        self._last_command = dt_util.now()
        try:
            await self.hass.services.async_call(svc_domain, service, {"entity_id": entity_id}, blocking=True)
        except Exception as err:  # noqa: BLE001 - show it instead of failing silently
            self._cmd_error = f"Could not switch {entity_id}: {err or type(err).__name__}"
            _LOGGER.warning("%s: %s", self.name, self._cmd_error)

    async def _drive_valves(self, d: logic.Decision, inp: logic.Inputs) -> bool:
        """Open the wanted zone; returns whether the pump may run yet (valve lead time)."""
        if not d.on or d.zone is None or d.zone >= len(self.zones):
            self._zone_since = None
            return d.on   # off, or a pump-only run (valves left as they are)
        zone_id = self.zones[d.zone]
        if self._bool(zone_id) is not True:
            await self._switch(zone_id, True, f"open zone {d.zone + 1}")
        if self._zone_since is None or self._zone_since[0] != d.zone:
            self._zone_since = (d.zone, inp.now)
            lead = float(self.settings["valve_lead_seconds"])
            if lead > 0 and not inp.is_on:
                async_call_later(self.hass, lead + 0.2, self._later)
        await self._close_valves(keep=d.zone)
        lead_ok = (inp.now - self._zone_since[1]).total_seconds() >= float(self.settings["valve_lead_seconds"])
        return lead_ok or bool(inp.is_on)

    async def _close_valves(self, keep: int | None) -> None:
        for i, z in enumerate(self.zones):
            if i != keep and self._bool(z):
                await self._switch(z, False, f"close zone {i + 1}")

    async def _later(self, _now) -> None:
        await self.async_evaluate()

    async def _alert(self, key: str, msg: str, status: str) -> None:
        now = dt_util.now()
        self.events.append({"t": now.isoformat(), "kind": key, "msg": msg})
        self.events = self.events[-30:]
        self._save()
        title = f"{self.name}: {status}" if key != "fault" else f"{self.name}: pump fault"
        try:
            await self.hass.services.async_call("persistent_notification", "create",
                                                {"title": title, "message": msg, "notification_id": f"{DOMAIN}_{self.entry.entry_id}_{key}"},
                                                blocking=False)
        except Exception:  # noqa: BLE001
            pass
        svc = self.settings.get("notify_service") or ""
        if svc.startswith("notify."):
            try:
                await self.hass.services.async_call("notify", svc.split(".", 1)[1], {"title": title, "message": msg}, blocking=False)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("%s: notify %s failed: %s", self.name, svc, err)

    # ------------------------------------------------------------ estimates
    def _power_estimate(self, inp: logic.Inputs) -> float | None:
        """Pump power: the meter, else the rating while running (scaled by speed for a VFD)."""
        if inp.power is not None:
            return max(inp.power, 0)
        if inp.running is None:
            return None
        if not inp.running:
            return 0.0
        rated = float(self.settings["rated_w"])
        if inp.hz is not None:
            return rated * min(max(inp.hz, 0) / 50, 1.2) ** 3
        return rated

    def _flow_estimate(self, inp: logic.Inputs) -> float | None:
        """L/min: the flow sensor, else the rated flow while running (scaled by speed for a VFD)."""
        if inp.flow is not None:
            return max(inp.flow, 0)
        if inp.running is None:
            return None
        if not inp.running:
            return 0.0
        rated = float(self.settings["flow_lpm"])
        return rated * min(max(inp.hz, 0) / 50, 1.2) if inp.hz is not None else rated

    def water_source(self) -> str:
        c = self.conf
        if c.get(CONF_WATER_TOTAL):
            return "meter"
        if c.get(CONF_FLOW):
            return "flow"
        return "estimate"

    # --------------------------------------------------------------- history
    def _sample(self) -> None:
        now = dt_util.now()
        live = self.live
        if not live:
            return
        day = now.date().isoformat()
        totals = self.daily.setdefault(day, {"run_s": 0.0, "starts": 0, "litres": 0.0, "kwh": 0.0})
        litres = 0.0
        if self._last_tick is not None:
            secs = min((now - self._last_tick).total_seconds(), 300)
            running = bool(live.get("running"))
            if running:
                totals["run_s"] += secs
            totals["kwh"] += (live.get("power_est") or 0) * secs / 3600 / 1000
            src = self.water_source()
            if src == "meter":
                total = self._float(self.conf.get(CONF_WATER_TOTAL), "water")
                if total is not None and self._last_total is not None and 0 <= total - self._last_total < 100000:
                    litres = total - self._last_total
                if total is not None:
                    self._last_total = total
            else:
                litres = (live.get("flow_est") or 0) * secs / 60
            totals["litres"] += litres
        elif self.water_source() == "meter":
            self._last_total = self._float(self.conf.get(CONF_WATER_TOTAL), "water")
        self._last_tick = now
        totals["starts"] = totals.get("starts", 0)
        if live.get("running") and not self.__dict__.get("_was_running_sample"):
            totals["starts"] += 1
        self.__dict__["_was_running_sample"] = bool(live.get("running"))

        slot = (now.hour * 60 + now.minute) // SAMPLE_MINUTES * SAMPLE_MINUTES
        b = self._bucket
        if b and (b["day"] != day or b["slot"] != slot):
            self._flush_bucket()
            b = self._bucket
        if not b:
            b.update({"day": day, "slot": slot, "n": 0, "run": 0, "level": None, "p": None, "pmax": None, "w": 0.0, "l": 0.0})
        b["n"] += 1
        b["run"] += 1 if live.get("running") else 0
        if live.get("level") is not None:
            b["level"] = live["level"]
        if live.get("pressure") is not None:
            b["p"] = live["pressure"]
        b["w"] += live.get("power_est") or 0
        b["l"] += litres

    def _bucket_row(self) -> list | None:
        b = self._bucket
        if not b or not b["n"]:
            return None
        n = b["n"]
        return [b["slot"], round(b["run"] / n, 2), None if b["level"] is None else round(b["level"], 1),
                None if b["p"] is None else round(b["p"], 2), round(b["w"] / n), round(b["l"], 1)]

    def _flush_bucket(self) -> None:
        row = self._bucket_row()
        if row is not None:
            rows = self.history.setdefault(self._bucket["day"], [])
            if rows and rows[-1][0] == row[0]:
                rows[-1] = row
            else:
                rows.append(row)
            self._prune()
            self._save(60)
        self._bucket = {}

    # ---------------------------------------------------------------- actions
    async def async_set_mode(self, mode: str, minutes: float | None = None, zone: int | None = None) -> None:
        if mode not in logic.MODES:
            raise ValueError(f"Unknown mode {mode}")
        if zone is not None and not 0 <= zone < len(self.zones):
            raise ValueError("No such zone")
        self.mode = mode
        if mode == "run":
            self.run_until = dt_util.now() + timedelta(minutes=minutes or self.settings["run_minutes"])
            self.manual_zone = zone if zone is not None else (0 if self.zones else None)
        else:
            self.run_until, self.manual_zone = None, None
        self._last_command = None  # a user action overrides anti-chatter
        self._save()
        await self.async_evaluate()

    async def async_reset(self) -> None:
        st = self.state
        st.fault, st.rest_until, st.rest_why, st.retries = None, None, "", 0
        st.timers.clear()
        st.level_ref = None
        st.alerts_sent.clear()
        self.events.append({"t": dt_util.now().isoformat(), "kind": "reset", "msg": "Fault reset"})
        self._last_command = None
        self._save()
        await self.async_evaluate()

    async def async_rain_delay(self, days: float) -> None:
        self.rain_delay_until = dt_util.start_of_local_day() + timedelta(days=days + 1) if days > 0 else None
        self._save()
        await self.async_evaluate()

    async def async_learn(self) -> dict:
        """Set dry-run / overload limits from the pump running normally right now."""
        inp = self.read_inputs()
        if not inp.running:
            raise ValueError("Start the pump and let it run normally first")
        new: dict = {}
        if inp.power is not None and inp.power > 50:
            new["dry_run_w"] = round(inp.power * 0.6)
            new["overload_w"] = round(inp.power * 1.4)
        if inp.amps is not None and inp.amps > 0.3:
            new["dry_run_a"] = round(inp.amps * 0.6, 1)
            new["overload_a"] = round(inp.amps * 1.4, 1)
        if not new:
            raise ValueError("No power or current sensor reading to learn from")
        await self.async_update_settings(new, True)
        return new

    async def async_update_settings(self, new: dict, admin: bool) -> None:
        cleaned = logic.validate_settings({**new}, admin)
        if "start_level" in cleaned or "stop_level" in cleaned:
            lo = cleaned.get("start_level", self.settings["start_level"])
            hi = cleaned.get("stop_level", self.settings["stop_level"])
            if lo >= hi:
                raise ValueError("Start level must be below the stop level")
        shed = cleaned.get("shed_below_kva", self.settings["shed_below_kva"])
        back = cleaned.get("restore_above_kva", self.settings["restore_above_kva"])
        if shed and back <= shed:
            raise ValueError("'Start again above' must be higher than 'Stop below' – leave room for the pump itself")
        self.settings.update(cleaned)
        self._save()
        await self.async_evaluate()

    # --------------------------------------------------------------- snapshot
    def snapshot(self, include_history: bool = False) -> dict:
        d = self.decision
        now = dt_util.now()
        c = self.conf
        today = now.date()
        nxt = None
        if self.pump_type == TYPE_IRRIGATION:
            nxt = logic.next_start(self.settings.get("programs", []), now)
        elif self.pump_type == TYPE_BOREHOLE and not any(c.get(k) for k in (CONF_TANK_LEVEL, CONF_TANK_FULL, CONF_TANK_LOW)):
            nxt = logic.next_start(self.settings.get("schedules", []), now)
        snap = {
            "entry_id": self.entry.entry_id,
            "name": self.name,
            "type": self.pump_type,
            "mode": self.mode,
            "run_until": self.run_until.isoformat() if self.run_until else None,
            "manual_zone": self.manual_zone,
            "rain_delay_until": self.rain_delay_until.isoformat() if self.rain_delay_until else None,
            "fault": self.state.fault,
            "rest_until": self.state.rest_until.isoformat() if self.state.rest_until else None,
            "decision": None if d is None else {
                "on": d.on, "status": d.status, "reason": d.reason, "source": d.source,
                "zone": d.zone, "program": d.program, "held": d.held,
            },
            "live": self.live,
            "today": {**{"run_s": 0, "starts": 0, "litres": 0, "kwh": 0}, **self.daily.get(today.isoformat(), {})},
            "next": nxt.isoformat() if nxt else None,
            "settings": self.settings,
            "zones": [self._zone_name(z) for z in self.zones],
            "events": list(reversed(self.events[-10:])),
            "features": {
                "switch": bool(c.get(CONF_PUMP_SWITCH)),
                "power": bool(c.get(CONF_PUMP_POWER)),
                "amps": bool(c.get(CONF_PUMP_CURRENT)),
                "hz": bool(c.get(CONF_PUMP_HZ)),
                "running": bool(c.get(CONF_RUNNING)),
                "vfd_fault": bool(c.get(CONF_VFD_FAULT)),
                "pressure": bool(c.get(CONF_PRESSURE)),
                "flow": bool(c.get(CONF_FLOW)),
                "meter": bool(c.get(CONF_WATER_TOTAL)),
                "level": bool(c.get(CONF_TANK_LEVEL)),
                "tank_full": bool(c.get(CONF_TANK_FULL)),
                "tank_low": bool(c.get(CONF_TANK_LOW)),
                "rain": bool(c.get(CONF_RAIN)),
                "load": bool(c.get(CONF_LOAD)),
                "water": self.water_source(),
            },
        }
        if include_history:
            rows = list(self.history.get(today.isoformat(), []))
            if (row := self._bucket_row()) is not None and self._bucket.get("day") == today.isoformat():
                rows = [r for r in rows if r[0] != row[0]] + [row]
            snap["history"] = {"today": rows, "yesterday": self.history.get((today - timedelta(days=1)).isoformat(), [])}
            snap["days"] = [{"day": (today - timedelta(days=n)).isoformat(),
                             **self.daily.get((today - timedelta(days=n)).isoformat(), {})} for n in range(13, -1, -1)]
            snap["sensors"] = {k: self._raw(c.get(k)) for k in [CONF_PUMP_SWITCH, *SENSOR_KEYS, CONF_RAIN] if c.get(k)}
        return snap

    def _zone_name(self, entity_id: str) -> str:
        st = self.hass.states.get(entity_id)
        return (st.attributes.get("friendly_name") if st else None) or entity_id

    def _raw(self, entity_id: str | None) -> str | None:
        st = self.hass.states.get(entity_id) if entity_id else None
        if st is None:
            return f"{entity_id} = missing"
        unit = st.attributes.get("unit_of_measurement") or ""
        return f"{entity_id} = {st.state} {unit}".strip()
