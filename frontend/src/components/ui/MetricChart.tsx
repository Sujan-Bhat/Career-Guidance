"use client";

/**
 * Multi-series line chart over session index (y is fixed to the FES 0..1
 * range). A sub-metric is genuinely absent in a session that never recorded
 * that activity, so nulls break the line into segments and leave a real gap —
 * plotting them as zero would invent a collapse that never happened.
 *
 * One series is one metric; several metrics share the chart so their shapes
 * can be read against each other. Hovering a point shows its session and value.
 */
export type ChartSeries = {
  key: string;
  label: string;
  color: string;
  strokeWidth?: number;
  values: (number | null)[];
};

const VIEW_W = 1000;
const PAD = { left: 46, right: 14, top: 14, bottom: 34 };

/** Contiguous runs of defined values, so gaps stay gaps. */
function segments(values: (number | null)[]) {
  const runs: { index: number; value: number }[][] = [];
  let run: { index: number; value: number }[] = [];
  values.forEach((value, index) => {
    if (value === null || Number.isNaN(value)) {
      if (run.length) runs.push(run);
      run = [];
    } else {
      run.push({ index, value });
    }
  });
  if (run.length) runs.push(run);
  return runs;
}

export function MetricChart({
  series,
  labels,
  height = 320,
  ariaLabel = "Sub-metric history",
}: {
  series: ChartSeries[];
  /** One label per session (shown as the x tick). */
  labels: string[];
  height?: number;
  ariaLabel?: string;
}) {
  const n = labels.length;
  const plotW = VIEW_W - PAD.left - PAD.right;
  const plotH = height - PAD.top - PAD.bottom;
  const xOf = (index: number) =>
    PAD.left + (n <= 1 ? plotW / 2 : (index / (n - 1)) * plotW);
  const yOf = (value: number) =>
    PAD.top + (1 - Math.max(0, Math.min(1, value))) * plotH;
  const tickStep = Math.max(1, Math.ceil(n / 8));

  return (
    <svg
      viewBox={`0 0 ${VIEW_W} ${height}`}
      role="img"
      aria-label={ariaLabel}
      className="h-auto w-full"
    >
      {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
        <g key={tick}>
          <line
            x1={PAD.left}
            y1={yOf(tick)}
            x2={PAD.left + plotW}
            y2={yOf(tick)}
            stroke="#e2e8f0"
            strokeWidth={1}
          />
          <text
            x={PAD.left - 10}
            y={yOf(tick) + 4}
            textAnchor="end"
            className="fill-slate-400"
            fontSize={11}
          >
            {tick.toFixed(2)}
          </text>
        </g>
      ))}

      {labels.map((label, index) =>
        index % tickStep === 0 ? (
          <text
            key={index}
            x={xOf(index)}
            y={height - 12}
            textAnchor="middle"
            className="fill-slate-400"
            fontSize={11}
          >
            {label}
          </text>
        ) : null,
      )}

      {series.map((s) => (
        <g key={s.key}>
          {segments(s.values).map((run, runIndex) =>
            run.length === 1 ? (
              <circle
                key={runIndex}
                cx={xOf(run[0].index)}
                cy={yOf(run[0].value)}
                r={3}
                fill={s.color}
              />
            ) : (
              <polyline
                key={runIndex}
                points={run.map((p) => `${xOf(p.index)},${yOf(p.value)}`).join(" ")}
                fill="none"
                stroke={s.color}
                strokeWidth={s.strokeWidth ?? 1.8}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            ),
          )}
          {s.values.map((value, index) =>
            value === null ? null : (
              <circle
                key={index}
                cx={xOf(index)}
                cy={yOf(value)}
                r={2.6}
                fill={s.color}
              >
                <title>{`${s.label} · session ${labels[index]} · ${value.toFixed(3)}`}</title>
              </circle>
            ),
          )}
        </g>
      ))}
    </svg>
  );
}
