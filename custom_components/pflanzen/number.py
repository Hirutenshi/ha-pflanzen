"""Configuration numbers on the device page: interval and winter factor."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INTERVAL, CONF_WINTER_FACTOR
from .coordinator import PflanzenConfigEntry
from .entity import PlantEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: PflanzenConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            SettingNumber(coordinator, CONF_INTERVAL, 1, 120, 0.5, UnitOfTime.DAYS),
            SettingNumber(coordinator, CONF_WINTER_FACTOR, 1, 3, 0.1, None),
        ]
    )


class SettingNumber(PlantEntity, NumberEntity):
    """Writes to the entry options; the update listener reloads the plant."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, key, minimum, maximum, step, unit) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> float:
        return float(self.coordinator.settings[self._key])

    async def async_set_native_value(self, value: float) -> None:
        entry = self.coordinator.config_entry
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, self._key: value}
        )
