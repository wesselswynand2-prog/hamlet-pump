"""Pure-logic tests: tank filling, protection, pressure pump, irrigation."""
from datetime import datetime, timedelta, timezone

import pytest

from custom_components.hamlet_pump import logic

T0 = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)   # a Monday


def S(**kw):
    return {**logic.DEFAULT_SETTINGS, **kw}


def run(inp_kw, s=None, st=None, now=T0):
    st = st or logic.State()
    d = logic.decide(logic.Inputs(now=now, **inp_kw), s or S(), st)
    return d, st


# ---------------------------------------------------------------- borehole
def test_fills_below_start_and_stops_at_stop():
    d, _ = run({"level": 35, "is_on": False, "running": False})
    assert d.on and d.status == "Filling"
    d, _ = run({"level": 70, "is_on": True, "running": True})
    assert d.on  # keeps filling between start and stop
    d, _ = run({"level": 70, "is_on": False, "running": False})
    assert not d.on and d.status == "Ready"
    d, _ = run({"level": 96, "is_on": True, "running": True})
    assert not d.on and d.status == "Tank full"


def test_full_float_overrides_level_and_manual_on():
    d, _ = run({"level": 50, "tank_full": True, "is_on": True, "running": True})
    assert not d.on
    d, _ = run({"mode": "on", "tank_full": True, "is_on": True, "running": True})
    assert not d.on and d.status == "Tank full"


def test_two_floats():
    d, _ = run({"tank_low": True, "tank_full": False, "is_on": False, "running": False})
    assert d.on
    d, _ = run({"tank_low": False, "tank_full": False, "is_on": True, "running": True})
    assert d.on   # keep filling up to the full float
    d, _ = run({"tank_low": False, "tank_full": False, "is_on": False, "running": False})
    assert not d.on


def test_single_full_float_waits_before_refill():
    st = logic.State()
    d, st = run({"tank_full": True, "is_on": True, "running": True}, st=st)
    assert not d.on
    d, st = run({"tank_full": False, "is_on": False, "running": False}, st=st, now=T0 + timedelta(minutes=1))
    assert not d.on and "refilling in" in d.reason
    d, st = run({"tank_full": False, "is_on": False, "running": False}, st=st, now=T0 + timedelta(minutes=17))
    assert d.on


def test_timer_without_sensors():
    d, _ = run({"is_on": False, "running": False}, now=T0.replace(hour=8, minute=30))
    assert d.on and d.source == "timer"
    d, _ = run({"is_on": False, "running": False}, now=T0.replace(hour=11))
    assert not d.on and "Next timer" in d.reason


def test_pumping_hours():
    s = S(hours_enabled=True, hours_start="06:00", hours_end="21:00")
    d, _ = run({"level": 10, "is_on": False, "running": False}, s=s, now=T0.replace(hour=22))
    assert not d.on and d.status == "Waiting"


def test_dry_run_rests_then_locks_out():
    s = S(dry_run_w=500, dry_run_seconds=15, max_retries=2, rest_minutes=30)
    st = logic.State()
    now = T0
    run({"level": 20, "is_on": True, "running": True, "power": 900}, s, st, now)
    now += timedelta(seconds=20)
    d, _ = run({"level": 20, "is_on": True, "running": True, "power": 300}, s, st, now)
    assert d.on  # timer just started
    now += timedelta(seconds=16)
    d, _ = run({"level": 20, "is_on": True, "running": True, "power": 300}, s, st, now)
    assert not d.on and d.status == "Resting" and d.alerts
    # still resting 10 min later
    d, _ = run({"level": 20, "is_on": False, "running": False}, s, st, now + timedelta(minutes=10))
    assert not d.on and d.status == "Resting"
    # after the rest it tries again
    now += timedelta(minutes=31)
    d, _ = run({"level": 20, "is_on": False, "running": False}, s, st, now)
    assert d.on
    for _ in range(2):  # fails twice more -> locked out
        run({"level": 20, "is_on": True, "running": True, "power": 300}, s, st, now)
        now += timedelta(seconds=11)
        run({"level": 20, "is_on": True, "running": True, "power": 300}, s, st, now)
        now += timedelta(seconds=16)
        d, _ = run({"level": 20, "is_on": True, "running": True, "power": 300}, s, st, now)
        now += timedelta(minutes=31)
        run({"level": 20, "is_on": False, "running": False}, s, st, now)
    assert st.fault and d.status == "Fault" and d.fault_new
    d, _ = run({"level": 20, "is_on": False, "running": False}, s, st, now + timedelta(hours=5))
    assert not d.on and d.status == "Fault"   # stays locked until Reset


def test_dry_run_ignored_during_start_grace():
    s = S(dry_run_w=500, dry_run_seconds=3, start_grace_seconds=10)
    st = logic.State()
    run({"level": 20, "is_on": True, "running": True, "power": 100}, s, st, T0)
    d, _ = run({"level": 20, "is_on": True, "running": True, "power": 100}, s, st, T0 + timedelta(seconds=8))
    assert d.on


def test_overload_latches():
    s = S(overload_a=10, overload_seconds=5)
    st = logic.State()
    run({"level": 20, "is_on": True, "running": True, "amps": 14}, s, st, T0)
    d, _ = run({"level": 20, "is_on": True, "running": True, "amps": 14}, s, st, T0 + timedelta(seconds=6))
    assert not d.on and st.fault and "Overload" in d.reason


def test_tank_not_filling_latches():
    s = S(no_rise_minutes=20)
    st = logic.State()
    run({"level": 30, "is_on": True, "running": True}, s, st, T0)
    d, _ = run({"level": 30.5, "is_on": True, "running": True}, s, st, T0 + timedelta(minutes=21))
    assert not d.on and "didn't fill" in d.reason


def test_level_rising_is_fine():
    s = S(no_rise_minutes=20)
    st = logic.State()
    for i in range(6):
        d, _ = run({"level": 30 + i * 2, "is_on": True, "running": True}, s, st, T0 + timedelta(minutes=i * 10))
    assert d.on


def test_borehole_rest_after_max_run():
    s = S(max_run_minutes=60, borehole_rest_minutes=30, no_rise_minutes=0)
    st = logic.State()
    run({"level": 20, "is_on": True, "running": True}, s, st, T0)
    d, _ = run({"level": 50, "is_on": True, "running": True}, s, st, T0 + timedelta(minutes=61))
    assert not d.on and "Resting the borehole" in d.reason
    d, _ = run({"level": 50, "is_on": False, "running": False}, s, st, T0 + timedelta(minutes=92))
    assert d.on


def test_anti_chatter_holds_but_not_protection():
    d, _ = run({"level": 30, "is_on": False, "running": False, "last_change": T0 - timedelta(seconds=10)})
    assert not d.on and d.held


def test_off_mode():
    d, _ = run({"mode": "off", "level": 10, "is_on": True, "running": True})
    assert not d.on and d.status == "Off"


def test_timed_run_and_expiry():
    d, _ = run({"mode": "run", "run_until": T0 + timedelta(minutes=5), "level": 80, "is_on": False, "running": False})
    assert d.on and d.source == "run"
    d, _ = run({"mode": "run", "run_until": T0 - timedelta(minutes=1), "level": 80, "is_on": True, "running": True})
    assert d.run_expired


# ------------------------------------------------------------------ booster
def B(**kw):
    return {"pump_type": "booster", "is_on": True, **kw}


def test_booster_standby_and_pumping():
    d, _ = run(B(running=False, hz=0, pressure=3.2))
    assert d.on and d.status == "Ready" and "vfd" in d.reason.lower()
    d, _ = run(B(running=True, hz=42, pressure=3.0, flow=18))
    assert d.on and d.status == "Pumping"


def test_booster_low_pressure_trip():
    s = S(low_pressure_bar=1.0, low_pressure_seconds=60)
    st = logic.State()
    run(B(running=True, pressure=0.3), s, st, T0)
    run(B(running=True, pressure=0.3), s, st, T0 + timedelta(seconds=11))
    d, _ = run(B(running=True, pressure=0.3), s, st, T0 + timedelta(seconds=72))
    assert not d.on and d.status == "Resting" and "burst" in d.reason


def test_booster_leak_alert_and_stop():
    s = S(max_continuous_minutes=30)
    st = logic.State()
    run(B(running=True), s, st, T0)
    d, _ = run(B(running=True), s, st, T0 + timedelta(minutes=31))
    assert d.on and any(k == "leak" for k, _ in d.alerts)
    d, _ = run(B(running=True), s, st, T0 + timedelta(minutes=32))
    assert not any(k == "leak" for k, _ in d.alerts)   # once per hour
    st = logic.State()
    s = S(max_continuous_minutes=30, leak_action="stop")
    run(B(running=True), s, st, T0)
    d, _ = run(B(running=True), s, st, T0 + timedelta(minutes=31))
    assert not d.on and st.fault


def test_booster_short_cycling_alert():
    s = S(max_starts_per_hour=5)
    st = logic.State()
    now = T0
    alerts = []
    for _ in range(7):
        d, _ = run(B(running=True), s, st, now); alerts += d.alerts
        now += timedelta(minutes=2)
        d, _ = run(B(running=False), s, st, now); alerts += d.alerts
        now += timedelta(minutes=2)
    assert any(k == "cycling" for k, _ in alerts)


def test_supply_tank_low_with_hysteresis():
    st = logic.State()
    d, _ = run(B(running=True, level=8), st=st)
    assert not d.on and d.status == "Tank low"
    d, _ = run(B(running=False, level=15), st=st)
    assert not d.on
    d, _ = run(B(running=False, level=21), st=st)
    assert d.on


def test_vfd_fault_reported_not_switched():
    d, _ = run(B(running=False, vfd_fault="code 7"))
    assert d.status == "VFD fault" and d.held and d.on


# --------------------------------------------------------------- irrigation
def I(**kw):
    return {"pump_type": "irrigation", "is_on": False, "running": False, "zone_count": 3, **kw}


PROG = S(programs=[{"enabled": True, "name": "Morning", "days": [0], "start": "05:00", "minutes": [10, 0, 15]}])


def test_program_zones_in_order_skipping_zero():
    d, _ = run(I(), PROG, now=T0.replace(hour=5, minute=3))
    assert d.on and d.zone == 0
    d, _ = run(I(), PROG, now=T0.replace(hour=5, minute=12))
    assert d.on and d.zone == 2      # zone 2 has 0 minutes
    d, _ = run(I(), PROG, now=T0.replace(hour=5, minute=26))
    assert not d.on and d.status == "Idle"
    d, _ = run(I(), PROG, now=(T0 + timedelta(days=1)).replace(hour=5, minute=3))
    assert not d.on   # Tuesday not selected


def test_program_past_midnight():
    s = S(programs=[{"enabled": True, "name": "Night", "days": [0], "start": "23:50", "minutes": [20]}])
    d, _ = run(I(zone_count=1), s, now=(T0 + timedelta(days=1)).replace(hour=0, minute=5))
    assert d.on


def test_rain_skip_and_delay():
    d, _ = run(I(rain=True), PROG, now=T0.replace(hour=5, minute=3))
    assert not d.on and d.status == "Rain skip"
    d, _ = run(I(rain_delay_until=T0 + timedelta(days=2)), PROG, now=T0.replace(hour=5, minute=3))
    assert not d.on and d.status == "Rain delay"


def test_manual_zone_run():
    d, _ = run(I(mode="run", run_until=T0 + timedelta(minutes=10), manual_zone=1))
    assert d.on and d.zone == 1


def test_validate_settings():
    assert logic.validate_settings({"start_level": 30}, admin=False) == {"start_level": 30}
    with pytest.raises(ValueError):
        logic.validate_settings({"dry_run_w": 300}, admin=False)
    with pytest.raises(ValueError):
        logic.validate_settings({"start_level": 90, "stop_level": 80}, admin=True)
    with pytest.raises(KeyError):
        logic.validate_settings({"nope": 1}, admin=True)
    p = logic.validate_settings({"programs": [{"name": "A", "days": [1], "start": "5:00", "minutes": [5, "10"]}]}, admin=False)
    assert p["programs"][0]["start"] == "05:00" and p["programs"][0]["minutes"] == [5.0, 10.0]
    with pytest.raises(ValueError):
        logic.validate_settings({"notify_service": "mobile"}, admin=True)


def test_stop_is_never_delayed_by_anti_chatter():
    d, _ = run({"level": 97, "is_on": True, "running": True, "last_change": T0 - timedelta(seconds=5)})
    assert not d.on and not d.held


def test_resume_filling_after_rest_between_levels():
    s = S(dry_run_w=500, dry_run_seconds=15, rest_minutes=30)
    st = logic.State()
    run({"level": 60, "is_on": True, "running": True, "power": 900}, s, st, T0)
    run({"level": 60, "is_on": True, "running": True, "power": 300}, s, st, T0 + timedelta(seconds=11))
    d, _ = run({"level": 60, "is_on": True, "running": True, "power": 300}, s, st, T0 + timedelta(seconds=27))
    assert d.status == "Resting"
    d, _ = run({"level": 60, "is_on": False, "running": False}, s, st, T0 + timedelta(minutes=31))
    assert d.on   # carries on filling to the stop level


# ---------------------------------------------------------------- load sharing
def test_load_sharing_two_pumps_drop_out_and_return_one_at_a_time():
    a = S(shed_below_kva=10, restore_above_kva=25, shed_seconds=10, restore_minutes=5)   # stops first
    b = S(shed_below_kva=5, restore_above_kva=18, shed_seconds=10, restore_minutes=8)    # stops last
    sa, sb = logic.State(), logic.State()
    base = {"mode": "on", "is_on": True, "running": True, "load_sensor": True}

    def step(spare, t):
        da = logic.decide(logic.Inputs(now=T0 + timedelta(seconds=t), spare_kva=spare, **base), a, sa)
        db = logic.decide(logic.Inputs(now=T0 + timedelta(seconds=t), spare_kva=spare, **base), b, sb)
        return da.on, db.on

    assert step(30, 0) == (True, True)
    assert step(8, 10) == (True, True)       # short dip (motor start) is ignored
    assert step(8, 25) == (False, True)      # stayed low 15 s -> pump A drops out
    assert step(3, 30) == (False, True)
    assert step(3, 45) == (False, False)     # still too little -> pump B too
    d = logic.decide(logic.Inputs(now=T0 + timedelta(seconds=45), spare_kva=3, **base), b, sb)
    assert d.status == "Load shed" and "3.0 kVA" in d.reason and d.tripped
    assert step(20, 60) == (False, False)    # B needs 18 kVA for 8 min, A needs 25
    assert step(20, 60 + 8 * 60 + 5) == (False, True)   # B back first
    assert step(26, 600) == (False, True)
    assert step(26, 600 + 5 * 60 + 5) == (True, True)


def test_load_sharing_off_without_sensor_or_levels():
    d, st = run({"mode": "on", "is_on": True, "running": True, "spare_kva": 1, "load_sensor": True})
    assert d.on and not st.shed           # levels 0 = off
    d, st = run({"mode": "on", "is_on": True, "running": True}, S(shed_below_kva=10, restore_above_kva=20))
    assert d.on                            # no sensor configured


def test_load_shed_meter_offline_keeps_pump_off_and_borehole_resumes():
    s = S(shed_below_kva=10, restore_above_kva=20, shed_seconds=0, restore_minutes=0)
    st = logic.State()
    d, st = run({"level": 60, "is_on": True, "running": True, "spare_kva": 4, "load_sensor": True}, s, st)
    assert not d.on and st.shed and st.resume
    d, st = run({"level": 60, "is_on": False, "running": False, "spare_kva": None, "load_sensor": True}, s, st, T0 + timedelta(minutes=1))
    assert not d.on and "isn't reporting" in d.reason
    d, st = run({"level": 60, "is_on": False, "running": False, "spare_kva": 22, "load_sensor": True}, s, st, T0 + timedelta(minutes=2))
    assert d.on and d.status == "Filling"   # carries on filling between start and stop level


def test_load_settings_validation():
    with pytest.raises(ValueError):
        logic.validate_settings({"shed_below_kva": 10, "restore_above_kva": 8}, True)
    assert logic.validate_settings({"load_mode": "used", "supply_kva": 100}, True)["load_mode"] == "used"
    with pytest.raises(ValueError):
        logic.validate_settings({"load_mode": "x"}, True)
