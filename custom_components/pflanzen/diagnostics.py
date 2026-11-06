"""Diagnostics download: settings, current state and the full event log."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import PflanzenConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PflanzenConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {"settings": coordinator.settings, "state": coordinator.plant.state.to_dict()}
