"""Actions (services) for several plants at once: pick plants, devices or areas.

Buttons act on one plant and report when nothing happened; these actions are
meant for "water everything listed" or "Wohnzimmer gegossen" and quietly skip
plants where an action does not apply (e.g. snooze on a plant that is still full).
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .coordinator import PlantCoordinator

ACTIONS = {
    "watered": lambda p, now, day: p.watered(now, day),
    "snooze": lambda p, now, day: p.snooze(now, day),
    "bone_dry": lambda p, now, day: p.watered(now, day, bone_dry=True),
    "undo": lambda p, now, day: p.undo(now),
    "fertilized": lambda p, now, day: p.fertilized(now) if p.config.fertilize else False,
}


def _coordinators(hass: HomeAssistant, entry_ids: set[str]) -> list[PlantCoordinator]:
    result = []
    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == DOMAIN and hasattr(entry, "runtime_data"):
            result.append(entry.runtime_data)
    return result


def async_setup_services(hass: HomeAssistant) -> None:
    async def handle(call: ServiceCall) -> ServiceResponse:
        coordinators = _coordinators(hass, await async_extract_config_entry_ids(call))
        if not coordinators:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_plants")
        action = ACTIONS[call.service]
        applied = []
        for coordinator in coordinators:
            if await coordinator.async_action(action) is not False:
                applied.append(coordinator.config_entry.title)
        return {"applied": sorted(applied)}

    for name in ACTIONS:
        hass.services.async_register(
            DOMAIN, name, handle, supports_response=SupportsResponse.OPTIONAL
        )
