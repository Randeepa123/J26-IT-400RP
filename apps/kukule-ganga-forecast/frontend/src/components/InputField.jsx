export default function InputField({ field, value, error, onChange }) {
  return (
    <div>
      <label htmlFor={field.key} className="mb-1 block text-sm font-medium text-slate-700">
        {field.label}
        {field.unit && <span className="text-slate-400"> ({field.unit})</span>}
      </label>
      <input
        id={field.key}
        type="number"
        inputMode="decimal"
        step={field.step}
        min={field.min}
        max={field.max}
        value={value}
        onChange={(e) => onChange(field.key, e.target.value)}
        placeholder={`${field.min} – ${field.max}`}
        aria-invalid={!!error}
        className={`w-full rounded-lg border px-3 py-2 text-sm shadow-sm outline-none transition focus:ring-2 ${
          error
            ? "border-red-400 focus:ring-red-200"
            : "border-slate-300 focus:border-sky-500 focus:ring-sky-200"
        }`}
      />
      <p className={`mt-1 min-h-[1rem] text-xs ${error ? "text-red-600" : "text-slate-400"}`}>
        {error || `Range: ${field.min} to ${field.max}`}
      </p>
    </div>
  );
}
