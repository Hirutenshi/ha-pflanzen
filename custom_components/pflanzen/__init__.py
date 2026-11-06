"""Pflanzen: water level, snooze and fertilizing reminders per plant."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_AREA, DOMAIN
from .coordinator import PflanzenConfigEntry, PlantCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PflanzenConfigEntry) -> bool:
    coordinator = PlantCoordinator(hass, entry)
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # One device per plant. The area is set only while the device has none,
    # so a later change on the device page is kept.
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Pflanzen",
        model="Zimmerpflanze",
    )
    if device.area_id is None and (area := coordinator.settings.get(CONF_AREA)):
        registry.async_update_device(device.id, area_id=area)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: PflanzenConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PflanzenConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PflanzenConfigEntry) -> None:
    """Deleting the plant also deletes its stored state and event log."""
    await PlantCoordinator(hass, entry).async_remove_store()
