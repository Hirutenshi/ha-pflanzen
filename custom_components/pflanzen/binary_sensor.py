"""Binary sensors: needs water, needs fertilizer."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import PflanzenConfigEntry
from .entity import PlantEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: PflanzenConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [NeedsWater(coordinator)]
    if coordinator.plant.config.fertilize:
        entities.append(NeedsFertilizer(coordinator))
    async_add_entities(entities)


class NeedsWater(PlantEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "needs_water")

    @property
    def is_on(self) -> bool:
        return self.plant.needs_water()


class NeedsFertilizer(PlantEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "needs_fertilizer")

    @property
    def is_on(self) -> bool:
        return self.plant.needs_fertilizer(dt_util.now())
