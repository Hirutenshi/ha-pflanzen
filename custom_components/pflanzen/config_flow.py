"""Config flow: one config entry per plant."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_AREA,
    CONF_FERTILIZE,
    CONF_FERTILIZE_WEEKS,
    CONF_INTERVAL,
    CONF_SEASON_END,
    CONF_SEASON_START,
    CONF_TEMPERATURE_ENTITY,
    CONF_WINTER_FACTOR,
    DEFAULTS,
    DOMAIN,
)

CONF_NAME = "name"


def _number(minimum: float, maximum: float, step: float, unit: str | None = None) -> selector.NumberSelector:
    config = selector.NumberSelectorConfig(
        min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX
    )
    if unit is not None:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


_MONTH = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[str(m) for m in range(1, 13)],
        translation_key="month",
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


def _plant_fields(values: dict[str, Any]) -> dict[Any, Any]:
    """Fields shared by setup and options, pre-filled from values."""

    def opt(key: str) -> vol.Optional:
        if values.get(key) is None:
            return vol.Optional(key)
        return vol.Optional(key, default=values[key])

    return {
        vol.Required(CONF_INTERVAL, default=values[CONF_INTERVAL]): _number(1, 120, 0.5, "d"),
        vol.Required(CONF_WINTER_FACTOR, default=values[CONF_WINTER_FACTOR]): _number(1, 3, 0.1),
        opt(CONF_AREA): selector.AreaSelector(),
        opt(CONF_TEMPERATURE_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(
                filter=[
                    selector.EntityFilterSelectorConfig(domain="climate"),
                    selector.EntityFilterSelectorConfig(domain="sensor", device_class="temperature"),
                ]
            )
        ),
        vol.Required(CONF_FERTILIZE, default=values[CONF_FERTILIZE]): selector.BooleanSelector(),
        vol.Required(CONF_FERTILIZE_WEEKS, default=values[CONF_FERTILIZE_WEEKS]): _number(1, 26, 1, "w"),
        vol.Required(CONF_SEASON_START, default=str(values[CONF_SEASON_START])): _MONTH,
        vol.Required(CONF_SEASON_END, default=str(values[CONF_SEASON_END])): _MONTH,
    }


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)
    data[CONF_SEASON_START] = int(data[CONF_SEASON_START])
    data[CONF_SEASON_END] = int(data[CONF_SEASON_END])
    return data


class PflanzenConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            name = user_input.pop(CONF_NAME).strip()
            await self.async_set_unique_id(slugify(name))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=name, data=_clean(user_input))

        schema = vol.Schema({vol.Required(CONF_NAME): selector.TextSelector(), **_plant_fields(DEFAULTS)})
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PflanzenOptionsFlow()


class PflanzenOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            data = _clean(user_input)
            # an optional field left empty must remove the old value
            for key in (CONF_AREA, CONF_TEMPERATURE_ENTITY):
                data.setdefault(key, None)
            return self.async_create_entry(data=data)

        current = {**DEFAULTS, **self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=vol.Schema(_plant_fields(current)))
