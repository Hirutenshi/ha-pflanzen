"""Buttons: watered, still moist (snooze), bone dry, undo, fertilized."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import PflanzenConfigEntry
from .entity import PlantEntity
from .model import Plant


@dataclass(frozen=True, kw_only=True)
class PlantButtonDescription(ButtonEntityDescription):
    action: Callable[[Plant, datetime, float | None], Any]
    needs_fertilize: bool = False


BUTTONS = (
    PlantButtonDescription(
        key="watered", icon="mdi:watering-can", action=lambda p, now, day: p.watered(now, day)
    ),
    PlantButtonDescription(
        key="snooze", icon="mdi:timer-sand", action=lambda p, now, day: p.snooze(now, day)
    ),
    PlantButtonDescription(
        key="bone_dry",
        icon="mdi:water-off-outline",
        action=lambda p, now, day: p.watered(now, day, bone_dry=True),
    ),
    PlantButtonDescription(key="undo", icon="mdi:undo", action=lambda p, now, day: p.undo(now)),
    PlantButtonDescription(
        key="fertilized",
        icon="mdi:sprout",
        action=lambda p, now, day: p.fertilized(now),
        needs_fertilize=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PflanzenConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        PlantButton(coordinator, d)
        for d in BUTTONS
        if not d.needs_fertilize or coordinator.plant.config.fertilize
    )


class PlantButton(PlantEntity, ButtonEntity):
    entity_description: PlantButtonDescription

    def __init__(self, coordinator, description: PlantButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        result = await self.coordinator.async_action(self.entity_description.action)
        # undo and snooze return False when they had nothing to do
        if result is False:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"{self.entity_description.key}_not_applied",
            )
