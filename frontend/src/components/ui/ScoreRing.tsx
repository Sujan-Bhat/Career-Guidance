/** Circular gauge for the FES display (0..1). */
export function ScoreRing({ value, label = "FES" }: { value: number | null; label?: string }) {
  const pct = value === null ? 0 : Math.max(0, Math.min(1, value)) * 100;
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="#e2e8f0" strokeWidth="12" />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke="#4f46e5"
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 70 70)"
        />
        <text x="70" y="70" textAnchor="middle" dominantBaseline="central" className="fill-slate-900 text-xl font-bold">
          {value === null ? "—" : `${(value * 100).toFixed(0)}%`}
        </text>
      </svg>
      <span className="text-sm font-medium text-slate-600">{label}</span>
    </div>
  );
}
