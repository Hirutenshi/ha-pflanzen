"""Plant care logic without any Home Assistant dependency.

The water level is tracked incrementally: every tick drains it by
100 % / effective interval per day. That keeps snooze, undo and later the
learned drain rate (v2) simple, and survives HA restarts because the time
since the last tick is used, not a fixed step.
"""

from __future__ import annotations

import calendar
import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

FULL = 100.0
DUE_SOON_LEVEL = 15.0
SNOOZE_DAYS = 2.0
UNDO_WINDOW = timedelta(hours=24)
CONVENIENCE_LEVEL = 30.0  # watered above this = not a signal for learning
MAX_EVENTS = 5000

# Event types (also the values written to the log)
WATERED = "watered"
SNOOZED = "snoozed"
BONE_DRY = "bone_dry"
FERTILIZED = "fertilized"
UNDONE = "undone"


def winter_blend(when: datetime, winter_factor: float) -> float:
    """Interval multiplier for the date: full factor Nov-Feb, linear in Oct and Mar."""
    if winter_factor == 1.0:
        return 1.0
    month = when.month
    if month in (11, 12, 1, 2):
        share = 1.0
    elif month in (10, 3):
        days = calendar.monthrange(when.year, month)[1]
        progress = (when.day - 1 + when.hour / 24) / days
        share = progress if month == 10 else 1.0 - progress
    else:
        share = 0.0
    return 1.0 + (winter_factor - 1.0) * share


def in_season(when: datetime, start_month: int, end_month: int) -> bool:
    """True if the month lies in [start, end]; supports seasons across New Year."""
    m = when.month
    if start_month <= end_month:
        return start_month <= m <= end_month
    return m >= start_month or m <= end_month


def next_season_start(when: datetime, start_month: int) -> datetime:
    year = when.year if when.month < start_month else when.year + 1
    return when.replace(year=year, month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)


@dataclass
class PlantConfig:
    interval_days: float
    winter_factor: float = 1.0
    fertilize: bool = False
    fertilize_weeks: float = 4.0
    season_start: int = 3
    season_end: int = 9


@dataclass
class PlantState:
    level: float = 0.0  # spec: every plant starts as due on day one
    updated: datetime | None = None
    empty_since: datetime | None = None
    last_watered: datetime | None = None
    last_fertilized: datetime | None = None
    temp_sum: float = 0.0  # hourly temperature samples since last watering
    temp_count: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    undo: list[dict[str, Any]] = field(default_factory=list)  # snapshots, newest last

    # --- persistence -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("updated", "empty_since", "last_watered", "last_fertilized"):
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlantState:
        data = dict(data)
        for key in ("updated", "empty_since", "last_watered", "last_fertilized"):
            if data.get(key):
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)


class Plant:
    """One plant: config + state + the operations behind the buttons."""

    def __init__(self, config: PlantConfig, state: PlantState | None = None) -> None:
        self.config = config
        self.state = state or PlantState()

    # --- derived values ----------------------------------------------------
    def effective_interval(self, now: datetime) -> float:
        return self.config.interval_days * winter_blend(now, self.config.winter_factor)

    def drain_per_day(self, now: datetime) -> float:
        return FULL / self.effective_interval(now)

    def days_left(self, now: datetime) -> float:
        return self.state.level / self.drain_per_day(now)

    def next_watering(self, now: datetime) -> datetime:
        return now + timedelta(days=self.days_left(now))

    def needs_water(self) -> bool:
        return self.state.level <= 0.0

    def due_soon(self) -> bool:
        return self.state.level < DUE_SOON_LEVEL

    def overdue_days(self, now: datetime) -> float:
        if self.state.empty_since is None:
            return 0.0
        return max(0.0, (now - self.state.empty_since).total_seconds() / 86400)

    def mean_temperature(self) -> float | None:
        if self.state.temp_count == 0:
            return None
        return self.state.temp_sum / self.state.temp_count

    def next_fertilizing(self, now: datetime) -> datetime | None:
        cfg = self.config
        if not cfg.fertilize:
            return None
        due = (
            self.state.last_fertilized + timedelta(weeks=cfg.fertilize_weeks)
            if self.state.last_fertilized
            else now
        )
        if not in_season(due, cfg.season_start, cfg.season_end):
            due = next_season_start(due, cfg.season_start)
        return due

    def needs_fertilizer(self, now: datetime) -> bool:
        due = self.next_fertilizing(now)
        return (
            due is not None
            and due <= now
            and in_season(now, self.config.season_start, self.config.season_end)
        )

    # --- time ----------------------------------------------------------------
    def tick(self, now: datetime, temperature: float | None = None) -> None:
        """Drain the level for the time since the last tick; sample the temperature."""
        st = self.state
        if st.updated is not None and now > st.updated:
            days = (now - st.updated).total_seconds() / 86400
            midpoint = st.updated + (now - st.updated) / 2
            rate = self.drain_per_day(midpoint)
            if st.level > 0.0 and st.level <= days * rate:
                # crossed zero during this tick: remember the exact moment
                st.empty_since = st.updated + timedelta(days=st.level / rate)
            st.level = max(0.0, st.level - days * rate)
        st.updated = now
        if st.level <= 0.0 and st.empty_since is None:
            st.empty_since = now
        if temperature is not None:
            st.temp_sum += temperature
            st.temp_count += 1

    # --- actions -------------------------------------------------------------
    def watered(self, now: datetime, day_length: float | None = None, bone_dry: bool = False) -> None:
        self.tick(now)
        self._snapshot(now)
        self._log(now, BONE_DRY if bone_dry else WATERED, day_length)
        st = self.state
        st.level = FULL
        st.empty_since = None
        st.last_watered = now
        st.temp_sum, st.temp_count = 0.0, 0

    def snooze(self, now: datetime, day_length: float | None = None) -> bool:
        """Checked, still moist: due again in exactly SNOOZE_DAYS. Never lowers the level."""
        self.tick(now)
        target = SNOOZE_DAYS * self.drain_per_day(now)
        if self.state.level >= target:
            return False
        self._snapshot(now)
        self._log(now, SNOOZED, day_length)
        self.state.level = target
        self.state.empty_since = None
        return True

    def fertilized(self, now: datetime) -> None:
        self.tick(now)
        self._snapshot(now)
        self._log(now, FERTILIZED, None)
        self.state.last_fertilized = now

    def undo(self, now: datetime) -> bool:
        """Restore the state before the last action, if it is at most 24 h old."""
        st = self.state
        if not st.undo:
            return False
        snap = st.undo[-1]
        if now - datetime.fromisoformat(snap["at"]) > UNDO_WINDOW:
            return False
        st.undo.pop()
        restored = PlantState.from_dict(snap["state"])
        events = st.events
        undo_stack = st.undo
        events.append({"ts": now.isoformat(), "type": UNDONE, "undid": snap["event"]})
        self.state = restored
        self.state.events = events[-MAX_EVENTS:]
        self.state.undo = undo_stack
        # the time between the action and the undo still counts
        self.state.updated = datetime.fromisoformat(snap["at"])
        self.tick(now)
        return True

    # --- internals -------------------------------------------------------------
    def _snapshot(self, now: datetime) -> None:
        snap_state = copy.deepcopy(self.state)
        snap_state.events, snap_state.undo = [], []
        self.state.undo.append({"at": now.isoformat(), "event": None, "state": snap_state.to_dict()})
        # keep only snapshots inside the undo window
        self.state.undo = [
            u for u in self.state.undo if now - datetime.fromisoformat(u["at"]) <= UNDO_WINDOW
        ]

    def _log(self, now: datetime, kind: str, day_length: float | None) -> None:
        event = {
            "ts": now.isoformat(),
            "type": kind,
            "level": round(self.state.level, 1),
            "interval": round(self.effective_interval(now), 2),
            "days_since_watered": (
                round((now - self.state.last_watered).total_seconds() / 86400, 2)
                if self.state.last_watered
                else None
            ),
            "temp_mean": round(t, 2) if (t := self.mean_temperature()) is not None else None,
            "day_length": round(day_length, 2) if day_length is not None else None,
        }
        self.state.events.append(event)
        self.state.events = self.state.events[-MAX_EVENTS:]
        self.state.undo[-1]["event"] = kind
