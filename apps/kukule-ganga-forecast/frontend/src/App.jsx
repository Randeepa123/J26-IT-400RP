import { useMemo, useState } from "react";
import InputField from "./components/InputField";
import ResultTable from "./components/ResultTable";
import { INPUT_FIELDS, MIN_INPUT_DATE, DAYS_AHEAD_OPTIONS } from "./config/ranges";
import { validateForm, validateField } from "./utils/validation";
import { requestForecast } from "./api/forecast";

// Today's date in the user's local timezone (YYYY-MM-DD).
const getToday = () => {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
const today = getToday();

const initialValues = {
  input_date: today,
  days_ahead: 1,
  ...Object.fromEntries(INPUT_FIELDS.map((f) => [f.key, ""])),
};

export default function App() {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");
  const [result, setResult] = useState(null);

  const fieldMap = useMemo(() => Object.fromEntries(INPUT_FIELDS.map((f) => [f.key, f])), []);

  const handleChange = (key, value) => {
    // Only today's date is allowed for the input date (no past or future dates).
    if (key === "input_date") value = today;
    setValues((v) => ({ ...v, [key]: value }));
    // live validation for the field being edited
    setErrors((prev) => {
      const next = { ...prev };
      let msg = "";
      if (fieldMap[key]) msg = validateField(fieldMap[key], value);
      else if (key === "input_date") msg = value && value >= MIN_INPUT_DATE ? "" : `Date must be on or after ${MIN_INPUT_DATE}.`;
      if (msg) next[key] = msg;
      else delete next[key];
      return next;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setApiError("");
    const found = validateForm(values);
    setErrors(found);
    if (Object.keys(found).length) {
      setResult(null);
      return;
    }

    const payload = {
      input_date: values.input_date,
      days_ahead: Number(values.days_ahead),
      ...Object.fromEntries(INPUT_FIELDS.map((f) => [f.key, Number(values[f.key])])),
    };

    try {
      setLoading(true);
      setResult(await requestForecast(payload));
    } catch (err) {
      setResult(null);
      setApiError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setValues(initialValues);
    setErrors({});
    setApiError("");
    setResult(null);
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Kukule Ganga Water Inflow Forecast</h1>
        <p className="mt-1 text-sm text-slate-500">
          Enter the observed reservoir and weather values for the input date, choose the forecast horizon, and run the prediction.
        </p>
      </header>

      <form onSubmit={handleSubmit} noValidate className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="input_date" className="mb-1 block text-sm font-medium text-slate-700">
              Input date
            </label>
            <input
              id="input_date"
              type="date"
              min={today}
              max={today}
              value={values.input_date}
              onChange={(e) => handleChange("input_date", e.target.value)}
              className={`w-full rounded-lg border px-3 py-2 text-sm shadow-sm outline-none focus:ring-2 ${
                errors.input_date ? "border-red-400 focus:ring-red-200" : "border-slate-300 focus:border-sky-500 focus:ring-sky-200"
              }`}
            />
            <p className={`mt-1 min-h-[1rem] text-xs ${errors.input_date ? "text-red-600" : "text-slate-400"}`}>
              {errors.input_date || "Only today's date is allowed"}
            </p>
          </div>

          <div>
            <label htmlFor="days_ahead" className="mb-1 block text-sm font-medium text-slate-700">
              Days ahead
            </label>
            <select
              id="days_ahead"
              value={values.days_ahead}
              onChange={(e) => handleChange("days_ahead", Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-200"
            >
              {DAYS_AHEAD_OPTIONS.map((d) => (
                <option key={d} value={d}>
                  {d} day{d > 1 ? "s" : ""} ahead
                </option>
              ))}
            </select>
            <p className="mt-1 min-h-[1rem] text-xs text-slate-400">Allowed: 1 to 7 days</p>
          </div>
        </div>

        <h2 className="mb-3 mt-5 text-sm font-semibold uppercase tracking-wide text-slate-500">Observed values</h2>
        <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {INPUT_FIELDS.map((f) => (
            <InputField key={f.key} field={f} value={values[f.key]} error={errors[f.key]} onChange={handleChange} />
          ))}
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-sky-600 px-5 py-2.5 text-sm font-semibold text-white shadow transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Predicting…" : "Run Prediction"}
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Reset
          </button>
        </div>

        {Object.keys(errors).length > 0 && (
          <p className="mt-3 text-sm text-red-600">Please fix the highlighted fields before running the prediction.</p>
        )}
      </form>

      {apiError && (
        <div role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {apiError}
        </div>
      )}

      {result && (
        <section className="mt-6">
          <h2 className="mb-3 text-lg font-semibold text-slate-900">Forecast result</h2>
          <ResultTable result={result} />
        </section>
      )}
    </div>
  );
}
