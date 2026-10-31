// Shows ONLY the requested output fields.
const ROWS = [
  "input_date",
  "forecast_date",
  "days_ahead",
  "history_method",
  "predicted_usable_inflow_m3s",
  "spill_probability_pct",
  "low_flow_probability_pct",
];

export default function ResultTable({ result }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full text-sm">
        <tbody className="divide-y divide-slate-100">
          {ROWS.map((key) => (
            <tr key={key}>
              <th scope="row" className="w-1/2 bg-slate-50 px-4 py-3 text-left font-mono text-xs font-semibold text-slate-600">
                {key}
              </th>
              <td className="px-4 py-3 font-mono text-slate-900">{String(result[key])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
