"""Constants for the Pflanzen integration."""

DOMAIN = "pflanzen"

CONF_AREA = "area"
CONF_INTERVAL = "interval_days"
CONF_WINTER_FACTOR = "winter_factor"
CONF_TEMPERATURE_ENTITY = "temperature_entity"
CONF_FERTILIZE = "fertilize"
CONF_FERTILIZE_WEEKS = "fertilize_weeks"
CONF_SEASON_START = "season_start"
CONF_SEASON_END = "season_end"

DEFAULTS = {
    CONF_INTERVAL: 10.0,
    CONF_WINTER_FACTOR: 1.3,
    CONF_FERTILIZE: False,
    CONF_FERTILIZE_WEEKS: 4.0,
    CONF_SEASON_START: 3,
    CONF_SEASON_END: 9,
}

STORAGE_VERSION = 1
