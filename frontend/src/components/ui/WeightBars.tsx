"use client";

/**
 * Grouped bars of Eq. 2 weight vectors: one group per sub-metric, one bar per
 * vector. Used to show which weight vector actually scored the sessions —
 * a student below the calibration gates is scored by the population vector,
 * so the two sets of bars are identical until calibration unlocks.
 */
const SUBMETRICS = ["tcr", "sci", "dfet", "qap", "lrds"] as const;

export type WeightVector = {
  label: string;
  color: string;
  weights: Record<string, number> | null;
};

export function WeightBars({ vectors }: { vectors: WeightVector[] }) {
  const width = 700;
  const height = 240;
  const left = 52;
  const right = 12;
  const top = 16;
  const bottom = 44;
  const plotW = width - left - right;
  const plotH = height - top - bottom;
  const groupW = plotW / SUBMETRICS.length;
  const barW = groupW / (vectors.length + 1);
  const yOf = (value: number) => top + (1 - Math.min(1, Math.max(0, value))) * plotH;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Applied weight vectors" className="h-auto w-full">
      {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
        <g key={tick}>
          <line x1={left} y1={yOf(tick)} x2={left + plotW} y2={yOf(tick)} stroke="#e2e8f0" strokeWidth={1} />
          <text x={left - 10} y={yOf(tick) + 4} textAnchor="end" className="fill-slate-400" fontSize={11}>
            {tick.toFixed(2)}
          </text>
        </g>
      ))}
      {SUBMETRICS.map((metric, group) => {
        const groupX = left + group * groupW;
        return (
          <g key={metric}>
            <text x={groupX + groupW / 2} y={height - 16} textAnchor="middle" className="fill-slate-500" fontSize={11}>
              {metric}
            </text>
            {vectors.map((vector, slot) => {
              if (!vector.weights) return null;
              const value = Number(vector.weights[metric] ?? 0);
              const barX = groupX + barW * (slot + 0.5);
              const barH = Math.max(1, value * plotH);
              return (
                <g key={vector.label}>
                  <rect
                    x={barX}
                    y={top + plotH - barH}
                    width={barW * 0.78}
                    height={barH}
                    rx={2}
                    fill={vector.color}
                    opacity={0.9}
                  >
                    <title>{`${vector.label} · ${metric} = ${value.toFixed(3)}`}</title>
                  </rect>
                  <text
                    x={barX + barW * 0.39}
                    y={top + plotH - barH - 4}
                    textAnchor="middle"
                    className="fill-slate-600"
                    fontSize={9}
                  >
                    {value.toFixed(2)}
                  </text>
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}
