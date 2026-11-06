"""Tests for the HA-independent plant logic."""

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Load model.py directly so the tests need no Home Assistant install.
_spec = importlib.util.spec_from_file_location(
    "pflanzen_model", Path(__file__).parents[1] / "custom_components/pflanzen/model.py"
)
m = importlib.util.module_from_spec(_spec)
sys.modules["pflanzen_model"] = m
_spec.loader.exec_module(m)

SUMMER = datetime(2026, 6, 1, 8, 0)
WINTER = datetime(2026, 12, 1, 8, 0)


def watered_plant(now, interval=10, winter=1.0, **kw):
    p = m.Plant(m.PlantConfig(interval_days=interval, winter_factor=winter, **kw))
    p.tick(now)
    p.watered(now)
    return p


def test_new_plant_starts_due():
    p = m.Plant(m.PlantConfig(interval_days=10))
    p.tick(SUMMER)
    assert p.needs_water()
    assert p.state.empty_since == SUMMER


def test_level_drains_linearly_and_stops_at_zero():
    p = watered_plant(SUMMER)
    p.tick(SUMMER + timedelta(days=5))
    assert p.state.level == pytest.approx(50)
    p.tick(SUMMER + timedelta(days=12))
    assert p.state.level == 0
    assert p.overdue_days(SUMMER + timedelta(days=14)) == pytest.approx(4)


def test_hourly_ticks_equal_one_big_tick():
    a, b = watered_plant(SUMMER), watered_plant(SUMMER)
    for h in range(1, 73):
        a.tick(SUMMER + timedelta(hours=h))
    b.tick(SUMMER + timedelta(hours=72))
    assert a.state.level == pytest.approx(b.state.level)


def test_winter_factor_blend():
    assert m.winter_blend(SUMMER, 2.0) == 1.0
    assert m.winter_blend(WINTER, 2.0) == 2.0
    assert m.winter_blend(datetime(2026, 10, 16), 2.0) == pytest.approx(1.48, abs=0.02)
    assert m.winter_blend(datetime(2026, 3, 16), 2.0) == pytest.approx(1.52, abs=0.02)
    p = watered_plant(WINTER, interval=10, winter=2.0)
    p.tick(WINTER + timedelta(days=10))
    assert p.state.level == pytest.approx(50)


def test_due_soon_threshold():
    p = watered_plant(SUMMER)
    p.tick(SUMMER + timedelta(days=8))  # 20 %
    assert not p.due_soon()
    p.tick(SUMMER + timedelta(days=9))  # 10 %
    assert p.due_soon() and not p.needs_water()


def test_snooze_sets_two_days_and_never_lowers():
    p = watered_plant(SUMMER)
    assert p.snooze(SUMMER + timedelta(days=1)) is False  # 90 % lasts longer than 2 days
    t = SUMMER + timedelta(days=11)
    p.tick(t)
    assert p.needs_water()
    assert p.snooze(t) is True
    assert p.days_left(t) == pytest.approx(2)
    assert p.state.empty_since is None
    assert p.state.events[-1]["type"] == m.SNOOZED


def test_bone_dry_refills_and_logs():
    p = watered_plant(SUMMER)
    t = SUMMER + timedelta(days=9)
    p.watered(t, bone_dry=True)
    assert p.state.level == 100
    ev = p.state.events[-1]
    assert ev["type"] == m.BONE_DRY
    assert ev["days_since_watered"] == pytest.approx(9)
    assert ev["level"] == pytest.approx(10)


def test_undo_restores_and_keeps_draining():
    p = watered_plant(SUMMER)
    t = SUMMER + timedelta(days=10)
    p.tick(t)
    p.watered(t)  # mistaken tap
    assert p.undo(t + timedelta(hours=2)) is True
    assert p.needs_water()
    assert p.state.last_watered == SUMMER
    assert p.state.events[-1]["type"] == m.UNDONE
    assert p.state.events[-1]["undid"] == m.WATERED


def test_undo_only_within_24h():
    p = watered_plant(SUMMER)
    assert p.undo(SUMMER + timedelta(hours=25)) is False


def test_temperature_mean_resets_on_watering():
    p = watered_plant(SUMMER)
    for h, temp in enumerate([20, 22, 24], start=1):
        p.tick(SUMMER + timedelta(hours=h), temp)
    assert p.mean_temperature() == pytest.approx(22)
    p.watered(SUMMER + timedelta(hours=4))
    assert p.state.events[-1]["temp_mean"] == pytest.approx(22)
    assert p.mean_temperature() is None


def test_fertilizing_pauses_outside_season():
    p = watered_plant(WINTER, fertilize=True)
    assert not p.needs_fertilizer(WINTER)
    assert p.next_fertilizing(WINTER) == datetime(2027, 3, 1)
    spring = datetime(2027, 3, 5)
    assert p.needs_fertilizer(spring)
    p.fertilized(spring)
    assert p.next_fertilizing(spring) == spring + timedelta(weeks=4)
    assert p.next_fertilizing(datetime(2027, 9, 20)) is not None


def test_fertilizing_off():
    p = watered_plant(SUMMER)
    assert p.next_fertilizing(SUMMER) is None and not p.needs_fertilizer(SUMMER)


def test_state_roundtrip():
    p = watered_plant(SUMMER, fertilize=True)
    p.fertilized(SUMMER + timedelta(days=1))
    restored = m.PlantState.from_dict(p.state.to_dict())
    assert restored == p.state
