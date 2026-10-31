import { INPUT_FIELDS, MIN_INPUT_DATE, DAYS_AHEAD_OPTIONS } from "../config/ranges";

/**
 * Validate the whole form. Returns an object of { fieldKey: "error message" }.
 * An empty object means the form is valid.
 */
export function validateForm(values) {
  const errors = {};

  if (!values.input_date) {
    errors.input_date = "Input date is required.";
  } else if (Number.isNaN(Date.parse(values.input_date))) {
    errors.input_date = "Enter a valid date.";
  } else if (values.input_date < MIN_INPUT_DATE) {
    errors.input_date = `Date must be on or after ${MIN_INPUT_DATE}.`;
  }

  if (!DAYS_AHEAD_OPTIONS.includes(Number(values.days_ahead))) {
    errors.days_ahead = `Select between ${DAYS_AHEAD_OPTIONS[0]} and ${DAYS_AHEAD_OPTIONS.at(-1)} days.`;
  }

  for (const f of INPUT_FIELDS) {
    const msg = validateField(f, values[f.key]);
    if (msg) errors[f.key] = msg;
  }

  return errors;
}

/** Validate a single numeric field (also used for live feedback while typing). */
export function validateField(field, raw) {
  if (raw === "" || raw === null || raw === undefined) return `${field.label} is required.`;
  const n = Number(raw);
  if (!Number.isFinite(n)) return "Enter a valid number.";
  if (n < field.min || n > field.max) return `Must be between ${field.min} and ${field.max}.`;
  return "";
}
