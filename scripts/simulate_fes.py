"""Replay a synthetic student through the REAL FES pipeline (read-only demo).

Feeds one StudentSimulator trajectory (30 sessions by default) through the
exact production functions the live system uses:

    simulator sessions
      -> compute_session_metrics   (trailing-14-day SCI window, LRDS thresholds)
      -> calibrate_student_weights (Eq. 2 replayed after EVERY session, so the
                                    cold-start -> personal-weight unlock is
                                    visible at the session it happens)
      -> compute_fes               (Eq. 1 under the population vector AND the
                                    student's own vector)

The population vector is read from the live `fes_weights` row with
student=None -- the same cold-start vector real users receive below the Eq. 2
gates. A uniform fallback is used when Mongo is unreachable.

Nothing is written to MongoDB: this is a diagnostic that answers "how would the
five sub-metrics evolve for a learner like this?". The optional --html report is
fully self-contained (inline SVG + CSS, no CDN, no JS) so it renders offline.

Usage:
    .venv/bin/python scripts/simulate_fes.py
    .venv/bin/python scripts/simulate_fes.py --sessions 60 --seed 7
    .venv/bin/python scripts/simulate_fes.py --html frontend/public/fes-simulation.html
    make simulate-fes           # terminal report
    make simulate-fes-html      # terminal report + chart page served at
                                # http://localhost:3000/fes-simulation.html
"""
from __future__ import annotations

import argparse
import html as html_module
import os
import pathlib
import sys
from datetime import datetime

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT / "ml", REPO_ROOT / "data" / "simulator"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from simulator import StudentSimulator  # noqa: E402

from careermind_ml.fes.engagement import engagement_signal  # noqa: E402
from careermind_ml.fes.pipeline import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    compute_session_metrics,
    load_config,
)
from careermind_ml.fes.weights import (  # noqa: E402
    SUBMETRICS,
    calibrate_student_weights,
    compute_fes,
)

BLOCKS = " .:-=+*#%@"
UNDEFINED_CHAR = "x"
WINDOW = 5  # sessions per window in the aggregate table
TREND = 10  # sessions per half in the first-vs-last trend
POPULATION_FALLBACK = 0.2  # uniform weight when the DB row is unavailable
CHART_COLORS = {
    "tcr": "#6366f1",
    "sci": "#0ea5e9",
    "dfet": "#10b981",
    "qap": "#f59e0b",
    "lrds": "#8b5cf6",
}
FES_COLOR = "#0f172a"
WEIGHT_COLORS = ("#94a3b8", "#0ea5e9", "#0f172a")  # population / at unlock / final


# --------------------------------------------------------------------- terminal


def population_weights(uri: str, db_name: str) -> dict:
    """The student=None cold-start vector from the live DB (uniform fallback)."""
    try:
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        row = client[db_name].fes_weights.find_one({"student": None})
        if row and row.get("weights"):
            return {m: float(row["weights"].get(m, POPULATION_FALLBACK)) for m in SUBMETRICS}
        print("(no population weights row found -- using uniform weights)")
    except Exception as exc:  # diagnostic path: never fail the whole run
        print(f"(population vector unavailable: {exc} -- using uniform weights)")
    return {m: POPULATION_FALLBACK for m in SUBMETRICS}


def fmt(value) -> str:
    return f"{value:5.2f}" if value is not None else "  .  "


def sparkline(values) -> str:
    present = [v for v in values if v is not None]
    if not present:
        return UNDEFINED_CHAR * len(values)
    low, high = min(present), max(present)
    span = (high - low) or 1.0
    chars = []
    for value in values:
        if value is None:
            chars.append(UNDEFINED_CHAR)
        else:
            idx = min(len(BLOCKS) - 1, int((value - low) / span * (len(BLOCKS) - 1) + 0.5))
            chars.append(BLOCKS[idx])
    return "".join(chars)


def mean_of(values):
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def gate_reason(pairs, weight_config) -> str:
    graded = [p for p in pairs if p.get("outcome") is not None]
    thin = [m for m in SUBMETRICS if sum(1 for p in pairs if p.get(m) is not None) < 3]
    reasons = []
    if len(pairs) < weight_config["min_sessions"]:
        reasons.append(f"sessions {len(pairs)}<{weight_config['min_sessions']}")
    if len(graded) < weight_config["min_graded_outcomes"]:
        reasons.append(f"graded {len(graded)}<{weight_config['min_graded_outcomes']}")
    if thin:
        reasons.append(",".join(thin) + " <3 obs")
    return "; ".join(reasons) or "all gates met"


# ------------------------------------------------------------------- html report


def _escape(text) -> str:
    return html_module.escape(str(text))


def _segments(values):
    """Contiguous (index, value) runs of defined values."""
    run: list = []
    for index, value in enumerate(values):
        if value is None:
            if run:
                yield run
                run = []
        else:
            run.append((index, value))
    if run:
        yield run


def _chart_svg(series, n_sessions: int, aria: str) -> str:
    """One SVG line chart: session index on x, [0, 1] on y, gaps stay gaps."""
    width, height = 980, 400
    left, right, top, bottom = 58, 20, 18, 54
    plot_w = width - left - right
    plot_h = height - top - bottom

    def x_of(index: float) -> float:
        return left + (index / max(n_sessions - 1, 1)) * plot_w

    def y_of(value: float) -> float:
        return top + (1.0 - value) * plot_h

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{_escape(aria)}" class="chart">']
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = y_of(tick)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{left - 12}" y="{y + 4:.1f}" class="axis" text-anchor="end">{tick:.2f}</text>')
    for index in range(0, n_sessions, 5):
        x = x_of(index)
        parts.append(f'<line x1="{x:.1f}" y1="{top + plot_h}" x2="{x:.1f}" y2="{top + plot_h + 6}" class="tick"/>')
        parts.append(f'<text x="{x:.1f}" y="{top + plot_h + 24}" class="axis" text-anchor="middle">s{index + 1}</text>')
    for name, values, color, stroke in series:
        for run in _segments(values):
            if len(run) == 1:
                index, value = run[0]
                parts.append(f'<circle cx="{x_of(index):.1f}" cy="{y_of(value):.1f}" r="3.2" fill="{color}"/>')
            else:
                points = " ".join(f"{x_of(i):.1f},{y_of(v):.1f}" for i, v in run)
                parts.append(
                    f'<polyline points="{points}" fill="none" stroke="{color}" '
                    f'stroke-width="{stroke}" stroke-linejoin="round" stroke-linecap="round"/>'
                )
    parts.append("</svg>")
    return "".join(parts)


def _weights_svg(vectors: list, labels: list, n_sessions_note: str) -> str:
    """Grouped bars: each sub-metric across the weight vectors in `vectors`."""
    width, height = 700, 260
    left, right, top, bottom = 56, 16, 16, 46
    plot_w = width - left - right
    plot_h = height - top - bottom
    group_w = plot_w / len(SUBMETRICS)
    bar_w = group_w / (len(vectors) + 1)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="FES weight vectors" class="chart">']
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = top + (1.0 - tick) * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{left - 12}" y="{y + 4:.1f}" class="axis" text-anchor="end">{tick:.2f}</text>')
    for group, metric in enumerate(SUBMETRICS):
        group_x = left + group * group_w
        parts.append(
            f'<text x="{group_x + group_w / 2:.1f}" y="{top + plot_h + 30}" class="axis" text-anchor="middle">'
            f"{metric}</text>"
        )
        for slot, weights in enumerate(vectors):
            if weights is None:
                continue
            value = float(weights.get(metric, 0.0))
            bar_x = group_x + bar_w * (slot + 0.5)
            bar_h = max(1.0, value * plot_h)
            parts.append(
                f'<rect x="{bar_x:.1f}" y="{top + plot_h - bar_h:.1f}" width="{bar_w * 0.8:.1f}" '
                f'height="{bar_h:.1f}" rx="2" fill="{WEIGHT_COLORS[slot % len(WEIGHT_COLORS)]}" opacity="0.9"/>'
            )
            parts.append(
                f'<text x="{bar_x + bar_w * 0.4:.1f}" y="{top + plot_h - bar_h - 5:.1f}" '
                f'class="barval" text-anchor="middle">{value:.2f}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _spark_svg(values, color: str) -> str:
    width, height, pad = 300, 30, 3
    present = [v for v in values if v is not None]
    if not present:
        return '<svg class="spark" viewBox="0 0 300 30"></svg>'
    low, high = min(present), max(present)
    span = (high - low) or 1.0

    def x_of(index: int) -> float:
        return pad + (index / max(len(values) - 1, 1)) * (width - 2 * pad)

    def y_of(value: float) -> float:
        return pad + (1.0 - (value - low) / span) * (height - 2 * pad)

    parts = ['<svg class="spark" viewBox="0 0 300 30" role="img">']
    for run in _segments(values):
        if len(run) == 1:
            index, value = run[0]
            parts.append(f'<circle cx="{x_of(index):.1f}" cy="{y_of(value):.1f}" r="2.4" fill="{color}"/>')
        else:
            points = " ".join(f"{x_of(i):.1f},{y_of(v):.1f}" for i, v in run)
            parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.8"/>')
    for index, value in enumerate(values):
        if value is None:
            parts.append(
                f'<line x1="{x_of(index):.1f}" y1="{height - pad:.1f}" x2="{x_of(index):.1f}" '
                f'y2="{height - 6:.1f}" class="undefined" stroke-width="1"/>'
            )
    parts.append("</svg>")
    return "".join(parts)


def render_html(
    *,
    seed: int,
    student: dict,
    sessions: list,
    per_session: list,
    population: dict,
    personal: list,
    unlock,
    pop_fes: list,
    own_fes: list,
    signals: list,
    weight_config: dict,
    pairs: list,
) -> str:
    count = len(sessions)
    series = [(m, [row[m] for row in per_session], CHART_COLORS[m], 1.8) for m in SUBMETRICS]
    series.append(("FES", pop_fes, FES_COLOR, 2.8))

    legend_rows = []
    for metric in SUBMETRICS:
        values = [row[metric] for row in per_session]
        present = [v for v in values if v is not None]
        spread = f"{min(present):.2f} – {max(present):.2f}" if present else "–"
        legend_rows.append(
            f'<li><span class="swatch" style="background:{CHART_COLORS[metric]}"></span>'
            f"<strong>{metric}</strong> {spread}"
            f' <span class="muted">undefined {sum(1 for v in values if v is None)}/{count}</span></li>'
        )
    legend_rows.append(
        f'<li><span class="swatch" style="background:{FES_COLOR}"></span><strong>FES</strong> '
        f"{min(pop_fes):.2f} – {max(pop_fes):.2f} <span class=\"muted\">population-weighted</span></li>"
    )

    spark_rows = []
    for metric in SUBMETRICS:
        values = [row[metric] for row in per_session]
        present = [v for v in values if v is not None]
        summary = (
            f"min {min(present):.2f} · mean {sum(present) / len(present):.2f} · max {max(present):.2f}"
            if present
            else "never defined"
        )
        spark_rows.append(
            f'<tr><th>{metric}</th><td>{_spark_svg(values, CHART_COLORS[metric])}</td>'
            f'<td class="muted">{summary}</td></tr>'
        )

    session_rows = []
    for index, (session, metrics) in enumerate(zip(sessions, per_session)):
        login = session["login_minute_of_day"]
        cells = "".join(
            f'<td class="num{"" if metrics[m] is not None else " undef"}">'
            f'{("—" if metrics[m] is None else f"{metrics[m]:.2f}")}</td>'
            for m in SUBMETRICS
        )
        own = own_fes[index]
        session_rows.append(
            f"<tr><td>{index + 1}</td><td>{session['date']}</td>"
            f"<td>{login // 60:02d}:{login % 60:02d}</td><td class='num'>{session['duration_minutes']:.0f}</td>"
            f"{cells}"
            f"<td class='num strong'>{pop_fes[index]:.2f}</td>"
            f"<td class='num'>{('—' if own is None else f'{own:.2f}')}</td>"
            f"<td class='num'>{signals[index]}</td>"
            f"<td class='num muted'>{session['assessment_score']:.1f}</td></tr>"
        )

    window_rows = []
    for start in range(0, count, WINDOW):
        stop = start + WINDOW
        cells = "".join(
            (lambda v: f"<td class='num{' undef' if v is None else ''}'>"
                       f"{('—' if v is None else f'{v:.2f}')}</td>")(mean_of([r[k] for r in per_session[start:stop]]))
            for k in SUBMETRICS
        )
        fes_cell = mean_of(pop_fes[start:stop])
        window_rows.append(
            f"<tr><td>s{start + 1:02d}–{min(stop, count):02d}</td>{cells}"
            f"<td class='num strong'>{fes_cell:.2f}</td></tr>"
        )

    half = min(TREND, count // 2) or 1
    trend_rows = []
    for metric in SUBMETRICS:
        values = [row[metric] for row in per_session]
        delta = mean_of(values[-half:]) - mean_of(values[:half])
        trend_rows.append(f"<tr><th>{metric}</th><td class='num'>{delta:+.3f}</td></tr>")
    trend_rows.append(
        f"<tr><th>FES</th><td class='num'>{mean_of(pop_fes[-half:]) - mean_of(pop_fes[:half]):+.3f}</td></tr>"
    )

    unlocked = unlock is not None
    unlock_label = f"session {unlock + 1}" if unlocked else "never"
    weight_vectors = [population]
    weight_labels = ["population"]
    if unlocked:
        weight_vectors.append(personal[unlock])
        weight_labels.append(f"personal @ unlock (s{unlock + 1})")
        weight_vectors.append(personal[-1])
        weight_labels.append("personal final")

    weights_legend = " ".join(
        f'<span class="swatch" style="background:{WEIGHT_COLORS[i % len(WEIGHT_COLORS)]}"></span> {_escape(label)}'
        for i, label in enumerate(weight_labels)
    )
    personal_unlock = " ".join(f"{m}={personal[unlock][m]:.3f}" for m in SUBMETRICS) if unlocked else "n/a"
    personal_final = " ".join(f"{m}={personal[-1][m]:.3f}" for m in SUBMETRICS) if unlocked else "n/a"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>FES simulation — seed {seed}, {count} sessions</title>
<style>
:root {{ color-scheme: light; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 32px 24px 64px; font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
        background: #f6f7fb; color: #0f172a; }}
main {{ max-width: 1040px; margin: 0 auto; }}
h1 {{ font-size: 22px; margin: 0 0 4px; letter-spacing: -0.01em; }}
h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: 0.08em; color: #475569;
      margin: 36px 0 12px; font-weight: 600; }}
.sub {{ color: #64748b; margin: 0 0 24px; }}
.card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px;
         box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); }}
.grid {{ stroke: #e2e8f0; stroke-width: 1; }}
.tick {{ stroke: #cbd5e1; stroke-width: 1; }}
.axis {{ fill: #94a3b8; font-size: 11px; font-variant-numeric: tabular-nums; }}
.barval {{ fill: #334155; font-size: 9px; }}
.chart {{ width: 100%; height: auto; display: block; }}
.spark {{ width: 300px; height: 30px; display: block; }}
.undefined {{ stroke: #fca5a5; }}
ul.legend {{ list-style: none; display: flex; flex-wrap: wrap; gap: 8px 20px; margin: 14px 0 0; padding: 0; }}
ul.legend li {{ display: flex; align-items: center; gap: 7px; }}
.swatch {{ width: 11px; height: 11px; border-radius: 3px; display: inline-block; }}
.muted {{ color: #94a3b8; }}
table {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #eef2f7; }}
thead th {{ position: sticky; top: 0; background: #fff; font-size: 11px; text-transform: uppercase;
            letter-spacing: 0.06em; color: #64748b; }}
td.num, th.num {{ text-align: right; }}
.undef {{ color: #cbd5e1; }}
.strong {{ font-weight: 600; }}
.scroll {{ max-height: 460px; overflow: auto; border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
@media (max-width: 780px) {{ .two {{ grid-template-columns: 1fr; }} }}
.kv {{ display: flex; flex-wrap: wrap; gap: 6px 18px; }}
.kv div {{ min-width: 190px; }}
.kv dt {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: #94a3b8; }}
.kv dd {{ margin: 2px 0 0; font-variant-numeric: tabular-nums; }}
code {{ background: #eef2f7; border-radius: 4px; padding: 1px 5px; }}
</style>
</head>
<body>
<main>
  <h1>Focus Efficiency Score — synthetic trajectory</h1>
  <p class="sub">One simulated student through the production FES pipeline · seed <strong>{seed}</strong>
    · <strong>{count}</strong> sessions · simulator → <code>compute_session_metrics</code> →
    <code>calibrate_student_weights</code> → <code>compute_fes</code> · regenerate with
    <code>make simulate-fes-html</code></p>

  <div class="card">
    <div class="kv">
      <div><dt>student latents</dt><dd>ability {student['ability']:.2f} · motivation {student['motivation']:.2f}
        · focus {student['focus_tendency']:.2f}</dd></div>
      <div><dt>population weights</dt><dd>{_escape(" ".join(f"{m}={population[m]:.3f}" for m in SUBMETRICS))}</dd></div>
      <div><dt>personal calibration</dt><dd>unlocked at <strong>{unlock_label}</strong></dd></div>
      <div><dt>personal @ unlock</dt><dd>{_escape(personal_unlock)}</dd></div>
      <div><dt>personal final</dt><dd>{_escape(personal_final)}</dd></div>
      <div><dt>engagement signal</dt><dd>{sum(signals)}/{count} sessions met the thresholds</dd></div>
    </div>
  </div>

  <h2>Sub-metric evolution</h2>
  <div class="card">
    {_chart_svg(series, count, "FES sub-metric evolution across sessions")}
    <ul class="legend">{''.join(legend_rows)}</ul>
  </div>

  <h2>Weight vectors (Eq. 2)</h2>
  <div class="card">
    {_weights_svg(weight_vectors, weight_labels, f"{count} sessions")}
    <p class="muted" style="margin:14px 0 0">{weights_legend} · bars are the Eq. 1 weights per sub-metric
      (population cold-start vs. this student's own vector once the gates pass)</p>
  </div>

  <h2>Sparklines</h2>
  <div class="card">
    <table><tbody>{''.join(spark_rows)}</tbody></table>
  </div>

  <h2>Per-session detail</h2>
  <div class="scroll">
    <table>
      <thead><tr>
        <th>#</th><th>date</th><th>login</th><th class="num">min</th>
        <th class="num">tcr</th><th class="num">sci</th><th class="num">dfet</th>
        <th class="num">qap</th><th class="num">lrds</th>
        <th class="num">FES</th><th class="num">own FES</th><th class="num">E</th><th class="num">outcome</th>
      </tr></thead>
      <tbody>{''.join(session_rows)}</tbody>
    </table>
  </div>

  <div class="two" style="margin-top:36px">
    <div>
      <h2 style="margin-top:0">{WINDOW}-session window means</h2>
      <div class="card">
        <table>
          <thead><tr><th>window</th>{''.join(f'<th class="num">{m}</th>' for m in SUBMETRICS)}<th class="num">FES</th></tr></thead>
          <tbody>{''.join(window_rows)}</tbody>
        </table>
      </div>
    </div>
    <div>
      <h2 style="margin-top:0">Trend (last {TREND} − first {TREND})</h2>
      <div class="card">
        <table><tbody>{''.join(trend_rows)}</tbody></table>
        <p class="muted" style="margin:14px 0 0">Read-only diagnostic: no documents are written to MongoDB.</p>
      </div>
    </div>
  </div>
</main>
</body>
</html>
"""


# ------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay one synthetic student through the real FES pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--sessions", type=int, default=30, help="sessions to simulate")
    parser.add_argument("--seed", type=int, default=42, help="simulator RNG seed")
    parser.add_argument("--uri", default=os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    parser.add_argument("--db", default=os.getenv("MONGO_DB_NAME", "careermind"))
    parser.add_argument(
        "--html",
        metavar="PATH",
        help="also write a self-contained HTML chart report (e.g. frontend/public/fes-simulation.html)",
    )
    args = parser.parse_args()

    config = load_config(DEFAULT_CONFIG_PATH)
    weight_config = config["weight_calibration"]

    sim = StudentSimulator(seed=args.seed)
    student = sim.generate_students(1)[0]
    sessions = sim.generate_sessions(student, n_sessions=args.sessions)

    # ---- real pipeline step 1: per-session sub-metrics with the trailing SCI window
    per_session = []
    for index, session in enumerate(sessions):
        session_date = datetime.fromisoformat(session["date"]).date()
        window = [
            w
            for w in sessions[: index + 1]
            if (session_date - datetime.fromisoformat(w["date"]).date()).days
            <= config["sci_window_days"]
        ]
        per_session.append(compute_session_metrics(session, window, config))

    # ---- real step 2: Eq. 2 calibration replayed after every session
    pairs = [{**m, "outcome": s["assessment_score"]} for m, s in zip(per_session, sessions)]
    personal = [calibrate_student_weights(pairs[: n + 1], weight_config) for n in range(len(sessions))]
    unlock = next((n for n, w in enumerate(personal) if w is not None), None)

    # ---- real step 3: Eq. 1 under both weight vectors
    population = population_weights(args.uri, args.db)
    pop_fes = [compute_fes(m, population) for m in per_session]
    own_fes = [compute_fes(m, personal[i]) if personal[i] else None for i, m in enumerate(per_session)]
    signals = [
        engagement_signal(
            s["duration_minutes"],
            interaction_count=s["interaction_count"],
            quiz_attempt_rate=min(1.0, (s["quiz_items"] or 0) / 5.0),
            interaction_rate=(s["interaction_count"] / s["duration_minutes"]) if s["duration_minutes"] > 0 else None,
        )
        for s in sessions
    ]

    print(f"STUDENT latents: ability={student['ability']:.2f} "
          f"motivation={student['motivation']:.2f} focus={student['focus_tendency']:.2f}")
    print("POPULATION weights: " + " ".join(f"{m}={population[m]:.3f}" for m in SUBMETRICS))
    if unlock is None:
        print(f"personal weights: NEVER unlocked ({gate_reason(pairs, weight_config)})")
    else:
        print(f"personal unlock at session {unlock + 1} of {len(sessions)}")
        print("PERSONAL weights at unlock: " + " ".join(f"{m}={personal[unlock][m]:.3f}" for m in SUBMETRICS))
        print("PERSONAL weights final:     " + " ".join(f"{m}={personal[-1][m]:.3f}" for m in SUBMETRICS))

    print()
    print("ss  date        login  dur  TCR   SCI   DFET  QAP   LRDS  | popFES selfFES  E  outcome")
    for index, (session, metrics) in enumerate(zip(sessions, per_session)):
        login = session["login_minute_of_day"]
        print(
            f"{index + 1:02d}  {session['date']}  {login // 60:02d}:{login % 60:02d}"
            f"  {session['duration_minutes']:3.0f}  "
            + "  ".join(fmt(metrics[m]) for m in SUBMETRICS)
            + f" |  {fmt(pop_fes[index])}    {fmt(own_fes[index])}    {signals[index]}"
            f"  {session['assessment_score']:5.1f}"
        )

    print()
    print(f"SPARKLINES over {len(sessions)} sessions ({UNDEFINED_CHAR} = undefined that session)")
    for metric in SUBMETRICS:
        values = [m[metric] for m in per_session]
        present = [v for v in values if v is not None]
        spread = f"[{min(present):.2f}..{max(present):.2f}]" if present else "[ - ]"
        print(f"  {metric:4s}: {sparkline(values)}   {spread}"
              f"  undefined {sum(1 for v in values if v is None)}/{len(values)}")
    print(f"  FES : {sparkline(pop_fes)}   [{min(pop_fes):.2f}..{max(pop_fes):.2f}]  population-weighted")
    own_present = [v for v in own_fes if v is not None]
    if own_present:
        label = f"  own-weighted from session {unlock + 1}"
        print(f"  oFES: {sparkline(own_fes)}   [{min(own_present):.2f}..{max(own_present):.2f}]{label}")
    else:
        print(f"  oFES: {sparkline(own_fes)}   personal weights never unlocked")

    print()
    print(f"{WINDOW}-SESSION WINDOW MEANS (mean over defined values):")
    print("      " + "".join(f"{m:>7}" for m in SUBMETRICS) + f"{'FES':>7}")
    for start in range(0, len(sessions), WINDOW):
        stop = start + WINDOW
        cells = [mean_of([m[k] for m in per_session[start:stop]]) for k in SUBMETRICS]
        cells.append(mean_of(pop_fes[start:stop]))
        rendered = "".join("      x" if c is None else f"{c:7.2f}" for c in cells)
        print(f"  s{start + 1:02d}-{min(stop, len(sessions)):02d}{rendered}")

    print()
    print(f"TREND (mean of last {TREND} sessions - mean of first {TREND}):")
    half = min(TREND, len(sessions) // 2) or 1
    for metric in SUBMETRICS:
        values = [m[metric] for m in per_session]
        delta = mean_of(values[-half:]) - mean_of(values[:half])
        print(f"  {metric:4s}: {delta:+.3f}")
    print(f"  FES : {mean_of(pop_fes[-half:]) - mean_of(pop_fes[:half]):+.3f}")
    print(f"  E   : {sum(signals)}/{len(signals)} sessions met the engagement signal")

    if args.html:
        report = render_html(
            seed=args.seed,
            student=student,
            sessions=sessions,
            per_session=per_session,
            population=population,
            personal=personal,
            unlock=unlock,
            pop_fes=pop_fes,
            own_fes=own_fes,
            signals=signals,
            weight_config=weight_config,
            pairs=pairs,
        )
        target = pathlib.Path(args.html)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report)
        print()
        print(f"HTML report written: {target}")
        try:
            relative = target.resolve().relative_to(REPO_ROOT / "frontend" / "public")
            print(f"view at: http://localhost:3000/{relative.as_posix()}")
        except ValueError:
            print("view at: open the file directly in a browser (outside frontend/public)")

    print()
    print("re-run with: .venv/bin/python scripts/simulate_fes.py "
          f"--seed {args.seed} --sessions {args.sessions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
