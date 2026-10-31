// Allowed ranges for every manual input (taken from the provided range table).
// `key` must match the raw input column names used by the trained models.
export const INPUT_FIELDS = [
  { key: "reservoir_inflow",      label: "Reservoir inflow",       unit: "m³/s", min: 5.15,  max: 585.07, step: "any" },
  { key: "reservoir_water_level", label: "Reservoir water level",  unit: "m",    min: 190,   max: 210,    step: "any" },
  { key: "reservoir_storage",     label: "Reservoir storage",      unit: "",     min: 1.0,   max: 2.0,    step: "any" },
  { key: "reservoir_outflow",     label: "Reservoir outflow",      unit: "m³/s", min: 4.0,   max: 600,    step: "any" },
  { key: "river_discharge",       label: "River discharge",        unit: "m³/s", min: 5.0,   max: 800.0,  step: "any" },
  { key: "rainfall",              label: "Rainfall",               unit: "mm",   min: 0,     max: 500,    step: "any" },
  { key: "temperature",           label: "Temperature",            unit: "°C",   min: 10,    max: 40,     step: "any" },
  { key: "humidity",              label: "Humidity",               unit: "%",    min: 50,    max: 98,     step: "any" },
  { key: "evaporation",           label: "Evaporation",            unit: "mm",   min: 1.5,   max: 7.0,    step: "any" },
  { key: "enso_index",            label: "ENSO index",             unit: "",     min: -1.7,  max: 2.6,    step: "any" },
  { key: "iod_index",             label: "IOD index",              unit: "",     min: -0.96, max: 1.27,   step: "any" },
];

// Earliest usable input date: the models need 75 days of history and the
// dataset starts on 2010-01-01, so the first valid origin date is 2010-03-16.
export const MIN_INPUT_DATE = "2010-03-16";

// Trained forecast horizons (days ahead).
export const DAYS_AHEAD_OPTIONS = [1, 2, 3, 4, 5, 6, 7];
