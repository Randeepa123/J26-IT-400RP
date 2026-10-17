# legacy_v1 - frozen v1 snapshot
Single-year LP / DQN work (Oct 2026, before the v2 redesign), kept so the v1 results can be reproduced.
- `Waterlevel_And_Demand/` - v1 scripts, audit reports, result CSVs, v1 datasets and v1 outputs. Run its scripts from inside that folder (as originally).
  Its configs point to `../../data_pipelines/rainfall_forecast/`. It carries its own copies of the station and demand datasets.
- `archive_removed_duplicates/` - duplicate or stale files removed earlier (see its MANIFEST.md).
The maintained project is in `../src`, `../data`, `../models`, `../outputs`, `../docs`.
v1 limitations (why v2 exists): trained on one fixed year, no forecasts/demand in the state, no reserve or terminal-storage rule, mandatory releases not enforced.
