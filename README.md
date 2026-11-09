# Pflanzen

Home Assistant custom integration for houseplant care: every plant gets a water level that drops every day, is refilled with one tap, and can be snoozed when the soil is still moist. Optional fertilizing schedule with a season. Built for one household; the spec lives in the Home Assistant Migration Plan ("Pflanzen-Spec" tab).

## Per plant (one device each)

| Entity | What it does |
| --- | --- |
| Wasserstand (%) | 100 % after watering, drops linearly to 0 % over the effective interval |
| Nächstes Gießen | when the level reaches 0 % |
| Braucht Wasser | on at 0 % |
| Gegossen / Noch feucht / Knochentrocken / Rückgängig | the four actions; snooze = off the "due soon" list for at least a day and empty no sooner than 2 days; undo works up to 24 h back |
| Gießintervall, Winterfaktor | editable on the device page |
| Nächstes Düngen, Düngen fällig, Gedüngt | only if fertilizing is on; pauses outside the season |

Effective interval = interval × winter factor (full November to February, blended in October and March).

Every action is logged with the level, the interval, the mean room temperature since the last watering and the day length, for learning the interval later (v2). The log is part of the integration's diagnostics download.

## Install

HACS → Custom repositories → this repo, category Integration → Download → restart HA → Settings → Devices & services → Add integration → Pflanzen (once per plant).

## Development

The plant logic in `custom_components/pflanzen/model.py` has no Home Assistant dependency and is tested with plain pytest:

```
python -m pytest tests
```
