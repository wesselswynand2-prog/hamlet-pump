"""Pure pump decision logic (no Home Assistant imports, so it is unit-testable).

Three kinds of installation:
  borehole   – fills a tank (JoJo) by level / floats / timer, with dry-run and borehole-rest protection
  booster    – house pressure pump (VFD or pressure switch); the app enables it and watches for
               dry-running, no pressure, leaks and short-cycling
  irrigation – watering programs over zones (valves), pump runs while a zone waters

Pressure is in bar, power in W, current in A, flow in L/min, tank level in %.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

MODES = ["auto", "run", "on", "off"]   # run = timed run (like the geyser's Boost)
LEAK_ACTIONS = ["alert", "stop"]

DEFAULT_SETTINGS: dict = {
    # General
    "rated_w": 1100,                 # used for energy when there is no power meter
    "flow_lpm": 40,                  # flow at full speed (50 Hz) – estimates water when there is no flow sensor / meter
    "running_above_w": 20,           # with a meter but no running signal: pump is running above this
    "min_switch_seconds": 30,        # protects relay and motor
    "start_grace_seconds": 10,       # ignore dry-run / pressure checks right after a start
    "run_minutes": 30,               # default timed run
    "notify_service": "",            # e.g. notify.mobile_app_wynand – faults are also sent here
    # Dry-run protection (0 = off)
    "dry_run_w": 0,
    "dry_run_a": 0,
    "dry_run_seconds": 15,
    "rest_minutes": 30,              # wait after a dry-run / no-pressure trip before trying again
    "max_retries": 3,                # then lock out until Reset
    "retries_reset_minutes": 5,      # a good run this long clears the retry count
    # Overload (0 = off)
    "overload_w": 0,
    "overload_a": 0,
    "overload_seconds": 5,
    # Borehole / tank filling
    "start_level": 40,
    "stop_level": 95,
    "float_restart_minutes": 15,     # only a 'full' float: wait this long after it drops before refilling
    "no_rise_minutes": 20,           # level must rise 1 % within this time while pumping (0 = off)
    "max_run_minutes": 180,          # then rest the borehole (0 = off)
    "borehole_rest_minutes": 30,
    "tank_litres": 5000,
    "hours_enabled": False,          # only pump inside these hours (noise, municipal rules)
    "hours_start": "06:00",
    "hours_end": "21:00",
    "schedules": [                   # timer, used when there is no level sensor and no floats
        {"enabled": True, "days": [0, 1, 2, 3, 4, 5, 6], "start": "08:00", "end": "10:00"},
    ],
    # Booster / pressure pump
    "low_pressure_bar": 0,           # running but pressure below this -> no water / burst pipe (0 = off)
    "low_pressure_seconds": 60,
    "max_continuous_minutes": 30,    # running non-stop this long -> possible leak (0 = off)
    "leak_action": "alert",          # alert | stop
    "max_starts_per_hour": 20,       # more -> short-cycling, check the pressure vessel (0 = off)
    # Supply tank (booster / irrigation draw from a tank)
    "supply_low_level": 10,
    "supply_restart_level": 20,
    # Irrigation
    "programs": [
        {"enabled": True, "name": "Morning", "days": [0, 2, 4], "start": "05:00", "minutes": [10]},
    ],
    "rain_skip": True,
    "valve_lead_seconds": 3,         # open the valve before the pump starts
    # Load sharing: stop the pump when the supply (transformer / NMD) has too little spare capacity
    "load_mode": "spare",            # spare = the load sensor shows spare kVA | used = it shows the load in use
    "supply_kva": 0,                 # 'used' mode: size of the supply (transformer / NMD) in kVA
    "shed_below_kva": 0,             # stop when spare capacity drops below this (0 = off)
    "restore_above_kva": 0,          # start again when spare capacity is back above this
    "shed_seconds": 10,              # spare must stay low this long (ignores motor-start peaks)
    "restore_minutes": 5,            # spare must stay high this long before restarting
}
LOAD_MODES = ["spare", "used"]

USER_KEYS = {
    "start_level", "stop_level", "hours_enabled", "hours_start", "hours_end", "schedules",
    "programs", "rain_skip", "run_minutes",
}

_NUM_RANGES = {
    "rated_w": (0, 30000), "flow_lpm": (0, 2000), "running_above_w": (0, 5000), "min_switch_seconds": (0, 3600),
    "start_grace_seconds": (0, 600), "run_minutes": (1, 720),
    "dry_run_w": (0, 30000), "dry_run_a": (0, 200), "dry_run_seconds": (3, 600), "rest_minutes": (1, 1440),
    "max_retries": (0, 20), "retries_reset_minutes": (1, 120),
    "overload_w": (0, 30000), "overload_a": (0, 200), "overload_seconds": (1, 120),
    "start_level": (0, 100), "stop_level": (1, 100), "float_restart_minutes": (0, 240), "no_rise_minutes": (0, 240),
    "max_run_minutes": (0, 1440), "borehole_rest_minutes": (1, 1440), "tank_litres": (0, 1_000_000),
    "low_pressure_bar": (0, 20), "low_pressure_seconds": (5, 3600), "max_continuous_minutes": (0, 1440),
    "max_starts_per_hour": (0, 600), "supply_low_level": (0, 100), "supply_restart_level": (0, 100),
    "valve_lead_seconds": (0, 60),
    "supply_kva": (0, 100000), "shed_below_kva": (0, 100000), "restore_above_kva": (0, 100000),
    "shed_seconds": (0, 600), "restore_minutes": (0, 240),
}
_BOOLS = {"hours_enabled", "rain_skip"}
_TIMES = {"hours_start", "hours_end"}


@dataclass
class Inputs:
    now: datetime
    pump_type: str = "borehole"
    mode: str = "auto"
    run_until: datetime | None = None
    manual_zone: int | None = None       # irrigation: zone for a timed run (None = pump only)
    has_switch: bool = True
    is_on: bool | None = None            # the relay
    running: bool | None = None          # actually pumping (VFD running / pressure switch closed / relay)
    last_change: datetime | None = None  # our own last switch command
    power: float | None = None
    amps: float | None = None
    hz: float | None = None
    pressure: float | None = None
    flow: float | None = None
    level: float | None = None
    tank_full: bool | None = None
    tank_low: bool | None = None
    vfd_fault: str | None = None
    rain: bool | None = None
    rain_delay_until: datetime | None = None
    zone_count: int = 0
    spare_kva: float | None = None       # spare supply capacity (from the load sensor)
    load_sensor: bool = False            # a load sensor is configured


@dataclass
class State:
    """Protection memory, kept by the controller between evaluations."""
    fault: str | None = None              # latched – only Reset clears it
    rest_until: datetime | None = None
    rest_why: str = ""
    retries: int = 0
    timers: dict = field(default_factory=dict)
    run_since: datetime | None = None
    was_running: bool = False
    level_ref: tuple | None = None        # (time, level) for the "tank not filling" check
    starts: list = field(default_factory=list)
    supply_low: bool = False
    full_since: datetime | None = None    # single full float: when it last dropped
    full_seen: bool = False
    resume: bool = False                  # a rest interrupted filling: carry on when it's over
    alerts_sent: dict = field(default_factory=dict)
    shed: bool = False                    # stopped for load sharing


@dataclass
class Decision:
    on: bool
    status: str               # short, for a badge
    reason: str               # one human sentence
    source: str | None = None  # level | float | timer | program | manual | run | standby
    zone: int | None = None    # irrigation zone to open
    program: str | None = None
    held: bool = False
    run_expired: bool = False
    tripped: bool = False      # protection stop: switch now, ignore anti-chatter
    alerts: list = field(default_factory=list)   # [(key, message)] new this evaluation
    fault_new: str | None = None


# ----------------------------------------------------------------- time helpers
def parse_hm(value: str) -> int:
    hours, minutes = str(value).split(":")[:2]
    return int(hours) * 60 + int(minutes)


def in_window(start: str, end: str, now: datetime, days: list | None = None) -> bool:
    s, e = parse_hm(start), parse_hm(end)
    minute = now.hour * 60 + now.minute
    days = list(range(7)) if days is None else days
    if s == e:
        return False
    if s < e:
        return now.weekday() in days and s <= minute < e
    if minute >= s:
        return now.weekday() in days
    return minute < e and (now.weekday() - 1) % 7 in days


def active_schedule(settings: dict, now: datetime) -> dict | None:
    for sched in settings.get("schedules", []):
        if sched.get("enabled", True) and in_window(sched["start"], sched["end"], now, sched.get("days")):
            return sched
    return None


def _at(day: datetime, hm: str) -> datetime:
    m = parse_hm(hm)
    return day.replace(hour=m // 60, minute=m % 60, second=0, microsecond=0)


def next_start(items: list, now: datetime) -> datetime | None:
    """Next start of any enabled schedule / program."""
    best = None
    for it in items:
        if not it.get("enabled", True):
            continue
        for offset in range(8):
            day = now + timedelta(days=offset)
            if day.weekday() not in it.get("days", list(range(7))):
                continue
            t = _at(day, it["start"])
            if t > now:
                if best is None or t < best:
                    best = t
                break
    return best


def program_minutes(program: dict, zone_count: int) -> list[float]:
    mins = [max(float(m or 0), 0) for m in program.get("minutes", [])]
    n = max(zone_count, 1)
    return (mins + [0.0] * n)[:n]


def program_now(settings: dict, now: datetime, zone_count: int) -> tuple[dict, int, datetime] | None:
    """(program, zone index, zone ends at) for the watering program running now, if any."""
    for prog in settings.get("programs", []):
        if not prog.get("enabled", True):
            continue
        mins = program_minutes(prog, zone_count)
        total = sum(mins)
        if total <= 0:
            continue
        for offset in (0, 1):  # started today, or yesterday and runs past midnight
            day = now - timedelta(days=offset)
            if day.weekday() not in prog.get("days", list(range(7))):
                continue
            t0 = _at(day, prog["start"])
            elapsed = (now - t0).total_seconds() / 60
            if not 0 <= elapsed < total:
                continue
            acc = 0.0
            for i, m in enumerate(mins):
                if m > 0 and elapsed < acc + m:
                    return prog, i, t0 + timedelta(minutes=acc + m)
                acc += m
    return None


def program_total(prog: dict, zone_count: int) -> float:
    return sum(program_minutes(prog, zone_count))


# ---------------------------------------------------------------- protection
def _timer(state: State, key: str, cond: bool, now: datetime) -> float:
    if not cond:
        state.timers.pop(key, None)
        return 0.0
    since = state.timers.setdefault(key, now)
    return (now - since).total_seconds()


def _alert(state: State, d_alerts: list, key: str, msg: str, now: datetime, every_min: float = 60) -> None:
    last = state.alerts_sent.get(key)
    if last is None or (now - last).total_seconds() >= every_min * 60:
        state.alerts_sent[key] = now
        d_alerts.append((key, msg))


def _fmt(v: float | None, unit: str, dec: int = 0) -> str:
    return "–" if v is None else f"{v:.{dec}f} {unit}".replace(" %", "%")


def _protect(inp: Inputs, s: dict, st: State, alerts: list) -> Decision | None:
    """Trips while the pump runs. Returns an off-decision when something tripped."""
    now = inp.now
    running = bool(inp.running)
    run_for = (now - st.run_since).total_seconds() if (running and st.run_since) else 0.0
    settled = run_for >= float(s["start_grace_seconds"])

    # overload -> latched
    over = running and (
        (inp.power is not None and s["overload_w"] > 0 and inp.power > s["overload_w"])
        or (inp.amps is not None and s["overload_a"] > 0 and inp.amps > s["overload_a"]))
    if _timer(st, "overload", over, now) >= float(s["overload_seconds"]):
        what = _fmt(inp.power, "W") if (inp.power is not None and s["overload_w"] > 0 and inp.power > s["overload_w"]) else _fmt(inp.amps, "A", 1)
        return _latch(st, f"Overload: pump drew {what}. Check for a seized pump or a faulty motor/capacitor, then press Reset.")

    # dry-run -> rest, retry, then latch
    low_p = inp.power is not None and s["dry_run_w"] > 0 and inp.power < s["dry_run_w"]
    low_a = inp.amps is not None and s["dry_run_a"] > 0 and inp.amps < s["dry_run_a"]
    if _timer(st, "dry", running and settled and (low_p or low_a), now) >= float(s["dry_run_seconds"]):
        what = _fmt(inp.power, "W") if low_p else _fmt(inp.amps, "A", 1)
        return _rest_retry(st, s, now, f"Dry-run: pump drew only {what}")

    # booster: running with no pressure -> no water / burst pipe
    lowpress = (running and settled and inp.pump_type == "booster" and inp.pressure is not None
                and s["low_pressure_bar"] > 0 and inp.pressure < s["low_pressure_bar"])
    if _timer(st, "lowpress", lowpress, now) >= float(s["low_pressure_seconds"]):
        return _rest_retry(st, s, now, f"Pressure stayed at {inp.pressure:.1f} bar while running – no water or a burst pipe")

    # a good run clears the retry count
    if running and run_for >= float(s["retries_reset_minutes"]) * 60 and not (low_p or low_a or lowpress):
        st.retries = 0

    if inp.pump_type == "borehole":
        # tank level must rise while pumping
        if running and inp.level is not None and s["no_rise_minutes"] > 0:
            if st.level_ref is None or inp.level >= st.level_ref[1] + 1:
                st.level_ref = (now, inp.level)
            elif (now - st.level_ref[0]).total_seconds() >= float(s["no_rise_minutes"]) * 60:
                return _latch(st, f"Tank didn't fill: level stayed at {inp.level:.0f}% for {s['no_rise_minutes']:.0f} min of pumping. "
                                  "Check for a dry borehole, a leaking pipe or a closed valve, then press Reset.")
        elif not running:
            st.level_ref = None
        # rest the borehole after a long run
        if running and s["max_run_minutes"] > 0 and run_for >= float(s["max_run_minutes"]) * 60:
            st.rest_until = now + timedelta(minutes=float(s["borehole_rest_minutes"]))
            st.rest_why = f"Resting the borehole after {s['max_run_minutes']:.0f} min of pumping"
            st.resume = True
            return Decision(False, "Resting", st.rest_why, tripped=True)

    if inp.pump_type == "booster":
        if running and s["max_continuous_minutes"] > 0 and run_for >= float(s["max_continuous_minutes"]) * 60:
            msg = f"Pump has run non-stop for {run_for / 60:.0f} min – possible leak, burst pipe or a tap left open"
            if s.get("leak_action") == "stop":
                return _latch(st, msg + ". Stopped – press Reset after checking.")
            _alert(st, alerts, "leak", msg, now)
        starts = len(st.starts)
        if s["max_starts_per_hour"] > 0 and starts > s["max_starts_per_hour"]:
            _alert(st, alerts, "cycling", f"Pump started {starts} times in the last hour – short-cycling. "
                                          "Check the pressure vessel's air charge and for a dripping tap or toilet.", now)
    return None


def _latch(st: State, msg: str) -> Decision:
    new = st.fault is None
    st.fault = msg
    st.timers.clear()
    return Decision(False, "Fault", msg, tripped=True, fault_new=msg if new else None)


def _rest_retry(st: State, s: dict, now: datetime, why: str) -> Decision:
    st.retries += 1
    st.timers.clear()
    if st.retries > int(s["max_retries"]):
        return _latch(st, f"{why}. Tripped {st.retries} times in a row – locked out. Check the water supply, then press Reset.")
    st.rest_until = now + timedelta(minutes=float(s["rest_minutes"]))
    st.resume = True
    st.rest_why = f"{why}. Trying again at {st.rest_until:%H:%M} (try {st.retries} of {int(s['max_retries'])})"
    d = Decision(False, "Resting", st.rest_why, tripped=True)
    d.alerts.append(("trip", st.rest_why))
    return d


# ------------------------------------------------------------------- decision
def decide(inp: Inputs, s: dict, st: State) -> Decision:
    now = inp.now
    running = bool(inp.running)
    # track starts / run time
    if running and not st.was_running:
        st.run_since = now
        st.starts.append(now)
    elif not running:
        st.run_since = None
    st.was_running = running
    st.starts = [t for t in st.starts if (now - t).total_seconds() < 3600]

    alerts: list = []
    d = _decide(inp, s, st, alerts)
    d.alerts = alerts + d.alerts
    if d.fault_new:
        d.alerts.append(("fault", d.fault_new))

    # anti-chatter: delay a RE-start shortly after we switched; stopping is always immediate
    if (not d.tripped and inp.is_on is False and d.on and inp.last_change is not None):
        wait = float(s["min_switch_seconds"]) - (now - inp.last_change).total_seconds()
        if wait > 0:
            d.held, d.on = True, inp.is_on
            d.reason += f" (waiting {wait:.0f}s to protect the relay)"
    return d


def _decide(inp: Inputs, s: dict, st: State, alerts: list) -> Decision:
    now = inp.now
    t = inp.pump_type

    if inp.mode == "off":
        return Decision(False, "Off", "Switched off – the pump won't run until you set it back to Auto")

    if st.fault:
        return Decision(False, "Fault", st.fault)

    if inp.vfd_fault:
        _alert(st, alerts, "vfd", f"VFD reports a fault: {inp.vfd_fault}", now)
        return Decision(bool(inp.is_on), "VFD fault", f"The VFD reports a fault: {inp.vfd_fault}. Check the drive's display.", held=True)

    trip = _protect(inp, s, st, alerts)
    if trip:
        return trip

    if st.rest_until:
        if now < st.rest_until:
            left = (st.rest_until - now).total_seconds() / 60
            return Decision(False, "Resting", f"{st.rest_why} – {left:.0f} min left")
        st.rest_until, st.rest_why = None, ""

    shed = _load_share(inp, s, st)
    if shed:
        return shed

    # booster / irrigation: protect the pump when its supply tank runs low
    if t in ("booster", "irrigation"):
        low = None
        if inp.level is not None:
            if inp.level <= s["supply_low_level"]:
                st.supply_low = True
            elif inp.level >= s["supply_restart_level"]:
                st.supply_low = False
            low = st.supply_low
        elif inp.tank_low is not None:
            low = st.supply_low = inp.tank_low
        if low:
            lvl = f" ({inp.level:.0f}%)" if inp.level is not None else ""
            _alert(st, alerts, "supply", f"Supply tank is low{lvl} – pump stopped to protect it", now, 360)
            return Decision(False, "Tank low", f"Supply tank is low{lvl} – pump stopped to protect it. "
                            + (f"Restarts at {s['supply_restart_level']:.0f}%." if inp.level is not None else "Restarts when the float says it has water."),
                            tripped=True)

    # borehole: a full tank always stops the pump (no overflow, even in On)
    if t == "borehole":
        full = inp.tank_full is True or (inp.level is not None and inp.level >= 99.5)
        if full and inp.mode in ("on", "run"):
            return Decision(False, "Tank full", "Tank is full – stopped to prevent overflow", source="float", run_expired=inp.mode == "run")

    if inp.mode == "run":
        if inp.run_until and now < inp.run_until:
            zone = inp.manual_zone if t == "irrigation" and inp.zone_count else None
            what = f"Watering zone {zone + 1}" if zone is not None else "Timed run"
            return Decision(True, "Running", f"{what} until {inp.run_until:%H:%M}", source="run", zone=zone)
        auto = _auto(inp, s, st)
        auto.run_expired = True
        return auto
    if inp.mode == "on":
        return Decision(True, "On", "Manual on – protection still active", source="manual")
    return _auto(inp, s, st)


def _load_share(inp: Inputs, s: dict, st: State) -> Decision | None:
    """Load sharing: stop while the supply has too little spare capacity, restart when it is back.

    Several pumps on one supply share it by giving each its own levels – the pump that should stop
    first gets the highest 'stop below' – so they drop out and come back one at a time.
    """
    below, back = float(s.get("shed_below_kva") or 0), float(s.get("restore_above_kva") or 0)
    if below <= 0 or not inp.load_sensor:
        st.shed = False
        return None
    now, spare = inp.now, inp.spare_kva
    back = max(back, below)
    if spare is not None:
        if not st.shed:
            if _timer(st, "shed", spare < below, now) >= float(s["shed_seconds"]):
                st.shed = True
                st.timers.pop("shed", None)
                if inp.running or inp.is_on:
                    st.resume = True    # carry on filling when the load is back down
        elif _timer(st, "unshed", spare >= back, now) >= float(s["restore_minutes"]) * 60:
            st.shed = False
            st.timers.pop("unshed", None)
    if not st.shed:
        return None
    if spare is None:
        return Decision(False, "Load shed", "Waiting for spare capacity – the load meter isn't reporting", tripped=True)
    if spare >= back:
        since = st.timers.get("unshed", now)
        left = float(s["restore_minutes"]) * 60 - (now - since).total_seconds()
        return Decision(False, "Load shed", f"Spare capacity back to {spare:.1f} kVA – restarting in {max(left, 0) / 60:.0f} min", tripped=True)
    return Decision(False, "Load shed", f"Only {spare:.1f} kVA spare on the supply – stopped to share the load. Restarts above {back:.0f} kVA.", tripped=True)


def _auto(inp: Inputs, s: dict, st: State) -> Decision:
    t = inp.pump_type
    now = inp.now
    if t == "booster":
        if inp.running:
            flow = f", {inp.flow:.0f} L/min" if inp.flow is not None else ""
            p = f" at {inp.pressure:.1f} bar" if inp.pressure is not None else ""
            return Decision(True, "Pumping", f"Supplying water{p}{flow}", source="standby")
        p = f" Pressure {inp.pressure:.1f} bar." if inp.pressure is not None else ""
        who = "The VFD" if inp.hz is not None else "The pressure switch"
        return Decision(True, "Ready", f"Standby – {who.lower()} starts the pump when a tap opens.{p}", source="standby")

    if t == "irrigation":
        if inp.rain_delay_until and now < inp.rain_delay_until:
            return Decision(False, "Rain delay", f"Watering paused until {inp.rain_delay_until:%a %d %b}")
        hit = program_now(s, now, inp.zone_count)
        if hit is None:
            return Decision(False, "Idle", "No watering program running")
        prog, zone, ends = hit
        name = prog.get("name") or "Program"
        if s.get("rain_skip") and inp.rain:
            return Decision(False, "Rain skip", f"{name}: skipped – the rain sensor is wet", program=name)
        what = f"zone {zone + 1}" if inp.zone_count else "watering"
        return Decision(True, "Watering", f"{name}: {what} until {ends:%H:%M}", source="program",
                        zone=zone if inp.zone_count else None, program=name)

    # borehole
    if s.get("hours_enabled") and not in_window(s["hours_start"], s["hours_end"], now):
        return Decision(False, "Waiting", f"Outside pumping hours ({s['hours_start']}–{s['hours_end']})")
    on = (bool(inp.is_on) if inp.has_switch else bool(inp.running)) or st.resume
    if inp.tank_full is True or (inp.level is not None and inp.level >= float(s["stop_level"])):
        st.resume = False
    if inp.tank_full is True:
        st.full_seen, st.full_since = True, None
        return Decision(False, "Tank full", "Tank is full (full float)", source="float")
    if inp.level is not None:
        lvl, start, stop = inp.level, float(s["start_level"]), float(s["stop_level"])
        if on and lvl < stop:
            return Decision(True, "Filling", f"Tank at {lvl:.0f}% – filling to {stop:.0f}%", source="level")
        if lvl <= start:
            return Decision(True, "Filling", f"Tank at {lvl:.0f}% – filling to {stop:.0f}%", source="level")
        if lvl >= stop:
            return Decision(False, "Tank full", f"Tank at {lvl:.0f}% – full", source="level")
        return Decision(False, "Ready", f"Tank at {lvl:.0f}% – refills below {start:.0f}%", source="level")
    if inp.tank_low is not None:
        if inp.tank_low:
            return Decision(True, "Filling", "Low float is down – filling until the tank is full", source="float")
        if on and inp.tank_full is not None:
            return Decision(True, "Filling", "Filling until the full float lifts", source="float")
        return Decision(False, "Ready", "Tank has water – waiting for the low float", source="float")
    if inp.tank_full is False:
        # only a full float: refill a while after it drops, so it doesn't chatter at the top
        if on:
            return Decision(True, "Filling", "Filling until the full float lifts", source="float")
        if st.full_since is None:
            st.full_since = now
        wait = float(s["float_restart_minutes"]) * 60 - (now - st.full_since).total_seconds()
        if st.full_seen and wait > 0:
            return Decision(False, "Ready", f"Full float dropped – refilling in {wait / 60:.0f} min", source="float")
        return Decision(True, "Filling", "Filling until the full float lifts", source="float")
    sched = active_schedule(s, now)
    if sched:
        return Decision(True, "Pumping", f"Timer {sched['start']}–{sched['end']}", source="timer")
    nxt = next_start(s.get("schedules", []), now)
    return Decision(False, "Idle", f"Next timer {nxt:%a %H:%M}" if nxt else "No level sensor or timer set")


# ------------------------------------------------------------------- settings
def _valid_days(v) -> list[int]:
    days = sorted({int(x) for x in v})
    if any(d < 0 or d > 6 for d in days):
        raise ValueError("days must be 0-6")
    return days


def validate_settings(new: dict, admin: bool) -> dict:
    out: dict = {}
    for key, value in new.items():
        if key not in DEFAULT_SETTINGS:
            raise KeyError(f"Unknown setting {key}")
        if not admin and key not in USER_KEYS:
            raise ValueError(f"Only an admin can change {key}")
        if key in _NUM_RANGES:
            lo, hi = _NUM_RANGES[key]
            v = float(value)
            if not lo <= v <= hi:
                raise ValueError(f"{key} must be between {lo} and {hi}")
            out[key] = int(v) if v.is_integer() else v
        elif key in _BOOLS:
            out[key] = bool(value)
        elif key in _TIMES:
            parse_hm(value)
            out[key] = str(value)[:5]
        elif key == "load_mode":
            if value not in LOAD_MODES:
                raise ValueError("load_mode must be spare or used")
            out[key] = value
        elif key == "leak_action":
            if value not in LEAK_ACTIONS:
                raise ValueError("leak_action must be alert or stop")
            out[key] = value
        elif key == "notify_service":
            v = str(value or "").strip()
            if v and not (v.startswith("notify.") and len(v) > 7):
                raise ValueError("Notify service must look like notify.mobile_app_phone")
            out[key] = v
        elif key == "schedules":
            out[key] = [{"enabled": bool(x.get("enabled", True)), "days": _valid_days(x.get("days", range(7))),
                         "start": _hm(x["start"]), "end": _hm(x["end"])} for x in value][:12]
        elif key == "programs":
            out[key] = [{"enabled": bool(x.get("enabled", True)), "name": str(x.get("name") or "Program")[:30],
                         "days": _valid_days(x.get("days", range(7))), "start": _hm(x["start"]),
                         "minutes": [max(0.0, min(float(m or 0), 240.0)) for m in x.get("minutes", [])][:16]} for x in value][:8]
    shed, back = out.get("shed_below_kva"), out.get("restore_above_kva")
    if shed and back is not None and back <= shed:
        raise ValueError("'Start again above' must be higher than 'Stop below' – leave room for the pump itself")
    lo = out.get("start_level", new.get("start_level"))
    hi = out.get("stop_level", new.get("stop_level"))
    if lo is not None and hi is not None and float(lo) >= float(hi):
        raise ValueError("Start level must be below the stop level")
    return out


def _hm(v: str) -> str:
    m = parse_hm(v)
    if not 0 <= m < 24 * 60:
        raise ValueError(f"Bad time {v}")
    return f"{m // 60:02d}:{m % 60:02d}"
