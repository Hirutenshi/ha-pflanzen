"""Coordinator: owns one plant, ticks it hourly and persists its state."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FERTILIZE,
    CONF_FERTILIZE_WEEKS,
    CONF_INTERVAL,
    CONF_SEASON_END,
    CONF_SEASON_START,
    CONF_TEMPERATURE_ENTITY,
    CONF_WINTER_FACTOR,
    DEFAULTS,
    DOMAIN,
    STORAGE_VERSION,
)
from .model import Plant, PlantConfig, PlantState

_LOGGER = logging.getLogger(__name__)

type PflanzenConfigEntry = ConfigEntry[PlantCoordinator]


def entry_settings(entry: ConfigEntry) -> dict[str, Any]:
    """Creation data overlaid with later option changes."""
    return {**DEFAULTS, **entry.data, **entry.options}


def plant_config(settings: dict[str, Any]) -> PlantConfig:
    return PlantConfig(
        interval_days=float(settings[CONF_INTERVAL]),
        winter_factor=float(settings[CONF_WINTER_FACTOR]),
        fertilize=bool(settings[CONF_FERTILIZE]),
        fertilize_weeks=float(settings[CONF_FERTILIZE_WEEKS]),
        season_start=int(settings[CONF_SEASON_START]),
        season_end=int(settings[CONF_SEASON_END]),
    )


class PlantCoordinator(DataUpdateCoordinator[None]):
    """Ticks the plant every hour; button presses go through async_action."""

    config_entry: PflanzenConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PflanzenConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(hours=1),
        )
        self.settings = entry_settings(entry)
        self.plant = Plant(plant_config(self.settings))
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )

    async def async_load(self) -> None:
        if (data := await self._store.async_load()) is not None:
            self.plant.state = PlantState.from_dict(data)

    async def async_remove_store(self) -> None:
        await self._store.async_remove()

    async def _async_update_data(self) -> None:
        self.plant.tick(dt_util.now(), self._temperature())
        await self._store.async_save(self.plant.state.to_dict())

    async def async_action(self, action: Callable[[Plant, datetime, float | None], Any]) -> Any:
        """Run a plant action, save, and push the new state to all entities."""
        now = dt_util.now()
        result = action(self.plant, now, self._day_length(now))
        await self._store.async_save(self.plant.state.to_dict())
        self.async_update_listeners()
        return result

    # --- inputs for the event log ------------------------------------------
    def _temperature(self) -> float | None:
        entity_id = self.settings.get(CONF_TEMPERATURE_ENTITY)
        if not entity_id or (state := self.hass.states.get(entity_id)) is None:
            return None
        raw = (
            state.attributes.get("current_temperature")
            if entity_id.startswith("climate.")
            else state.state
        )
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _day_length(self, now: datetime) -> float | None:
        sunrise = get_astral_event_date(self.hass, SUN_EVENT_SUNRISE, now.date())
        sunset = get_astral_event_date(self.hass, SUN_EVENT_SUNSET, now.date())
        if sunrise is None or sunset is None:
            return None
        return (sunset - sunrise).total_seconds() / 3600
