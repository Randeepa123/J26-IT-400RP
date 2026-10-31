const BASE_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

/**
 * POST the form to the backend and return the forecast summary.
 * Expected response keys:
 *   input_date, forecast_date, days_ahead, history_method, scenarios_used,
 *   predicted_usable_inflow_m3s, spill_probability_pct, low_flow_probability_pct
 */
export async function requestForecast(payload) {
  const res = await fetch(`${BASE_URL}/api/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON response */
  }

  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
        ? detail.map((d) => d.msg).join("; ")
        : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data;
}
