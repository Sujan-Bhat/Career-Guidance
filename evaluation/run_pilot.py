#!/usr/bin/env python
"""Pilot-study runner (paper Sec. VIII) — prints tables and writes results JSON.

Studies:
  fes-validity   FES/sub-metric correlation with held-out grades;
                 per-student vs population weight vectors
  benchmark      3-stage cascade vs kg_only / cf_only / fm_only / popularity
                 (leave-one-out over interactions; P@10 / R@10 / nDCG@10 / Hit@10)
  dqn            DQN convergence summary from the saved training curve
  sensitivity    threshold & reward-weight sweeps (paper Sec. VIII #4)

Usage:
    PYTHONPATH=ml:evaluation python evaluation/run_pilot.py [--study benchmark ...]
    make eval
"""
import argparse
import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS_PATH = ROOT / "evaluation" / "results" / "pilot_results.json"

STUDIES = ("fes-validity", "benchmark", "dqn", "sensitivity")


# ----------------------------------------------------------------- helpers

def _pearson(xs: list, ys: list) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx > 0 and dy > 0 else None


def _fmt(value, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _print_table(headers: list, rows: list) -> None:
    widths = [
        max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h))
        for i, h in enumerate(headers)
    ]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("-" * len(line))
    for row in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(row, widths)))


# ----------------------------------------------------------------- studies

def study_fes_validity() -> dict:
    """Study 1: FES (and each sub-metric) vs held-out academic outcomes,
    split by weight-vector source (per-student Eq. 2 vs population fallback)."""
    import os

    from pymongo import MongoClient

    from careermind_ml.fes.weights import SUBMETRICS

    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    db = client[os.getenv("MONGO_DB_NAME", "careermind")]

    grades_by_student: dict[str, list[float]] = {}
    for profile in db.profiles.find({}, {"academic_records": 1, "external_id": 1}):
        student = profile.get("external_id") or str(profile.get("_id", ""))
        values = [r.get("grade") for r in profile.get("academic_records") or [] if r.get("grade") is not None]
        if values:
            grades_by_student[student] = values

    # per-student applied weights vs the stored population vector
    population_weights = (db.fes_weights.find_one({"student": None}) or {}).get("weights") or {}

    metrics_by_student: dict[str, dict] = {}
    for row in db.fes_history.find(
        {}, {"student": 1, "fes": 1, **{m: 1 for m in SUBMETRICS}, "weights": 1}
    ):
        bucket = metrics_by_student.setdefault(
            row["student"], {"fes": [], **{m: [] for m in SUBMETRICS}, "per_student_weights": False}
        )
        if row.get("fes") is not None:
            bucket["fes"].append(row["fes"])
        for m in SUBMETRICS:
            if row.get(m) is not None:
                bucket[m].append(row[m])
        weights = row.get("weights") or {}
        if population_weights and any(
            abs(float(weights.get(m, 0)) - float(population_weights.get(m, 0))) > 1e-6
            for m in SUBMETRICS
        ):
            bucket["per_student_weights"] = True

    students = []
    for student, agg in metrics_by_student.items():
        if student not in grades_by_student:
            continue
        students.append(
            {
                "student": student,
                "grade": statistics.fmean(grades_by_student[student]),
                "fes": statistics.fmean(agg["fes"]) if agg["fes"] else None,
                **{m: statistics.fmean(agg[m]) if agg[m] else None for m in SUBMETRICS},
                "weights": "per-student" if agg["per_student_weights"] else "population",
            }
        )

    def correlations(group: list) -> dict:
        out = {}
        for metric in ("fes", *SUBMETRICS):
            xs = [s[metric] for s in group if s.get(metric) is not None]
            ys = [s["grade"] for s in group if s.get(metric) is not None]
            out[metric] = _pearson(xs, ys)
        return out

    per_student_group = [s for s in students if s["weights"] == "per-student"]
    population_group = [s for s in students if s["weights"] == "population"]

    result = {
        "n_students": len(students),
        "n_per_student_weights": len(per_student_group),
        "n_population_weights": len(population_group),
        "all": correlations(students),
        "per_student_weights": correlations(per_student_group),
        "population_weights": correlations(population_group),
    }

    print(f"\n### FES predictive validity (Pearson r vs mean grade, n={len(students)})\n")
    _print_table(
        ["metric", "all", "per-student w", "population w"],
        [
            [m, _fmt(result["all"][m]), _fmt(result["per_student_weights"][m]),
             _fmt(result["population_weights"][m])]
            for m in ("fes", *SUBMETRICS)
        ],
    )
    print(
        f"\nweight vectors: {len(per_student_group)} students per-student (Eq. 2), "
        f"{len(population_group)} on population fallback"
    )
    return result


def study_benchmark() -> dict:
    """Study 2: cascade vs single-technique baselines (leave-one-out)."""
    from benchmark import build_context, run_benchmark

    print("\n### Recommender benchmark (leave-one-out over interactions)\n")
    context = build_context()
    result = run_benchmark(context, top_k=10)
    rows = [
        [
            technique,
            _fmt(metrics["precision@k"]),
            _fmt(metrics["recall@k"]),
            _fmt(metrics["ndcg@k"]),
            _fmt(metrics["hit@k"]),
        ]
        for technique, metrics in result["metrics"].items()
    ]
    _print_table(["technique", "P@10", "R@10", "nDCG@10", "Hit@10"], rows)
    print(
        f"\nstudents evaluated: {result['n_students']} | train interactions: "
        f"{context['n_train_interactions']} | holdouts: {context['n_holdouts']}"
    )
    print(
        f"stage-1 gate @{result.get('threshold') or 0.60}: "
        f"mean {result['mean_candidates']:.1f} of {len(context['candidates'])} pathways pass"
    )
    return result


def study_dqn() -> dict:
    """Study 3: DQN convergence from the saved training curve."""
    path = ROOT / "ml" / "artifacts" / "dqn_training.json"
    if not path.exists():
        print("\n### DQN convergence\n\nNo training curve found — run `make train-dqn` first.")
        return {"available": False}

    payload = json.loads(path.read_text())
    rewards = payload.get("rewards") or []
    if not rewards:
        print("\n### DQN convergence\n\nTraining curve empty.")
        return {"available": False}

    window = min(50, len(rewards))
    first = statistics.fmean(rewards[:window])
    last = statistics.fmean(rewards[-window:])
    summary = {
        "available": True,
        "episodes": len(rewards),
        "mean_reward_first": round(first, 4),
        "mean_reward_last": round(last, 4),
        "improvement": round(last - first, 4),
        "final_epsilon": payload.get("final_epsilon"),
        "total_steps": payload.get("total_steps"),
        "reward_weights": payload.get("reward_weights"),
    }
    print("\n### DQN convergence (Eq. 3 reward)\n")
    _print_table(
        ["episodes", "steps", "first-50 mean", "last-50 mean", "Δ", "final ε"],
        [[summary["episodes"], summary["total_steps"], _fmt(first), _fmt(last),
          _fmt(summary["improvement"]), _fmt(summary["final_epsilon"], 3)]],
    )
    return summary


def study_sensitivity() -> dict:
    """Study 4: sweep design thresholds and Eq. 3 reward weights."""
    import sensitivity

    grids = sensitivity.default_grids()
    result = {}
    print("\n### Sensitivity analysis (paper Sec. VIII #4)\n")
    for parameter, values in grids.items():
        print(f"  sweep: {parameter} = {values}")
        table = sensitivity.sweep(parameter, values)
        result[parameter] = table
        metric_names = list(next(iter(table.values())).keys())
        _print_table(
            [parameter, *metric_names],
            [[str(value), *[_fmt(row.get(m)) for m in metric_names]] for value, row in table.items()],
        )
        print()
    return result


# --------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description="CAREERMIND pilot study (paper Sec. VIII)")
    parser.add_argument("--study", action="append", choices=STUDIES, help="run only this study (repeatable)")
    parser.add_argument("--out", default=str(RESULTS_PATH), help="results JSON path")
    args = parser.parse_args()

    studies = args.study or list(STUDIES)
    results = {"studies": {}}

    dispatch = {
        "fes-validity": study_fes_validity,
        "benchmark": study_benchmark,
        "dqn": study_dqn,
        "sensitivity": study_sensitivity,
    }
    for study in studies:
        print(f"\n{'=' * 70}\n{study}\n{'=' * 70}")
        results["studies"][study] = dispatch[study]()

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nresults written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
