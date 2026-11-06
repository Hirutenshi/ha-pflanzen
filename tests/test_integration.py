"""End-to-end tests against a real (test) Home Assistant instance."""

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er, area_registry as ar
from pytest_homeassistant_custom_component.common import async_fire_time_changed

DOMAIN = "pflanzen"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def _add_plant(hass: HomeAssistant, name="Monstera", **extra):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    data = {
        "name": name,
        "interval_days": 10,
        "winter_factor": 1.0,
        "fertilize": False,
        "fertilize_weeks": 4,
        "season_start": "3",
        "season_end": "9",
        **extra,
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


def _eid(hass, entry, platform, key):
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")


async def _press(hass, entity_id):
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done()


async def test_setup_creates_device_in_area_and_entities(hass: HomeAssistant):
    area = ar.async_get(hass).async_create("Wohnzimmer")
    entry = await _add_plant(hass, area=area.id)

    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    assert device.name == "Monstera" and device.area_id == area.id

    level = _eid(hass, entry, "sensor", "water_level")
    assert hass.states.get(level).state == "0.0"  # starts as due
    assert hass.states.get(_eid(hass, entry, "binary_sensor", "needs_water")).state == "on"
    # fertilizing is off: no fertilizer entities
    assert _eid(hass, entry, "button", "fertilized") is None
    assert _eid(hass, entry, "sensor", "next_fertilizing") is None


async def test_water_drain_snooze_undo(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    freezer.move_to("2026-06-01 08:00:00+02:00")
    entry = await _add_plant(hass)
    level = _eid(hass, entry, "sensor", "water_level")

    await _press(hass, _eid(hass, entry, "button", "watered"))
    assert hass.states.get(level).state == "100.0"
    assert hass.states.get(_eid(hass, entry, "binary_sensor", "needs_water")).state == "off"

    # snooze is refused while the level still lasts longer than 2 days
    with pytest.raises(ServiceValidationError):
        await _press(hass, _eid(hass, entry, "button", "snooze"))

    # 5 days later the hourly update has drained it to 50 %
    freezer.tick(timedelta(days=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert float(hass.states.get(level).state) == pytest.approx(50, abs=0.5)

    # a mistaken second watering can be undone
    await _press(hass, _eid(hass, entry, "button", "watered"))
    await _press(hass, _eid(hass, entry, "button", "undo"))
    assert float(hass.states.get(level).state) == pytest.approx(50, abs=0.5)


async def test_state_survives_reload(hass: HomeAssistant):
    entry = await _add_plant(hass)
    await _press(hass, _eid(hass, entry, "button", "watered"))
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert float(hass.states.get(_eid(hass, entry, "sensor", "water_level")).state) > 99


async def test_interval_number_updates_options(hass: HomeAssistant):
    entry = await _add_plant(hass)
    number = _eid(hass, entry, "number", "interval_days")
    await hass.services.async_call("number", "set_value", {"entity_id": number, "value": 14}, blocking=True)
    await hass.async_block_till_done()
    assert entry.options["interval_days"] == 14
    assert hass.states.get(number).state == "14.0"


async def test_fertilizing_entities_and_duplicate_name(hass: HomeAssistant):
    entry = await _add_plant(hass, name="Gummibaum", fertilize=True)
    assert _eid(hass, entry, "button", "fertilized") is not None
    assert _eid(hass, entry, "binary_sensor", "needs_fertilizer") is not None

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Gummibaum", "interval_days": 10, "winter_factor": 1.0, "fertilize": False,
         "fertilize_weeks": 4, "season_start": "3", "season_end": "9"},
    )
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"


async def test_options_flow_changes_area_and_temperature(hass: HomeAssistant):
    entry = await _add_plant(hass)
    hass.states.async_set("sensor.flur_temp", "19.5", {"device_class": "temperature"})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"interval_days": 12, "winter_factor": 1.5, "temperature_entity": "sensor.flur_temp",
         "fertilize": False, "fertilize_weeks": 4, "season_start": "3", "season_end": "9"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.settings["temperature_entity"] == "sensor.flur_temp"
    assert entry.runtime_data.plant.config.interval_days == 12
