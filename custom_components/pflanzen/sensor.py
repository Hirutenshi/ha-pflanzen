"""Sensors: water level, next watering, next fertilizing."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import PflanzenConfigEntry
from .entity import PlantEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: PflanzenConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [WaterLevelSensor(coordinator), NextWateringSensor(coordinator)]
    if coordinator.plant.config.fertilize:
        entities.append(NextFertilizingSensor(coordinator))
    async_add_entities(entities)


class WaterLevelSensor(PlantEntity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "water_level")

    @property
    def native_value(self) -> float:
        return round(self.plant.state.level, 1)

    @property
    def icon(self) -> str:
        level = self.plant.state.level
        if level <= 0:
            return "mdi:water-off"
        if self.plant.due_soon():
            return "mdi:water-alert"
        return "mdi:water"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        now = dt_util.now()
        p = self.plant
        last = p.state.last_watered
        return {
            "due_soon": p.due_soon(),
            "overdue_days": round(p.overdue_days(now), 1),
            "effective_interval": round(p.effective_interval(now), 1),
            "last_watered": last.isoformat() if last else None,
            "temperature_mean": round(t, 1) if (t := p.mean_temperature()) is not None else None,
        }


class NextWateringSensor(PlantEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:watering-can"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "next_watering")

    @property
    def native_value(self) -> datetime:
        now = dt_util.now()
        return self.plant.next_watering(now).replace(microsecond=0)


class NextFertilizingSensor(PlantEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:sprout"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "next_fertilizing")

    @property
    def native_value(self) -> datetime | None:
        due = self.plant.next_fertilizing(dt_util.now())
        return due.replace(microsecond=0) if due else None
