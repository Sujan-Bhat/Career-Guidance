#!/usr/bin/env python
"""Map OULAD CSV tables into CAREERMIND MongoDB collections (Phase 1).

Mapping (see data/oulad/README.md):
    studentInfo.csv      -> profiles (one per student; demographic + final_result)
    studentVle.csv       -> sessions (one per student-day) + events (one per VLE row)
    studentAssessment.csv-> profiles.academic_records (grades for Eq. 2 calibration)
    vle.csv              -> resources (id_site + activity_type -> resource type)

Documented OULAD gaps (filled by data/simulator/simulator.py instead):
    * no task start/completion granularity        -> TCR
    * no quiz item-level re-attempt data          -> QAP
    * no skill-assessment scores                  -> RL state / ensemble features
    * no career outcomes or preferences           -> ensemble labels
    * no session boundaries (day-level clicks only) -> session durations approximated

Dates: OULAD `date` is days since presentation start. Each presentation is
anchored to a nominal calendar date ("B" -> Feb 3, "J" -> Oct 7 of its year).

Usage:
    python data/oulad/map_oulad.py [--raw-dir data/oulad/raw/] [--uri ...] [--db careermind]
                                   [--limit-students 200] [--with-events]
"""
import argparse
import csv
import pathlib
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

# activity_type -> CAREERMIND resource type (LRDS uses type-specific dwell thresholds)
ACTIVITY_TYPE_MAP = {
    "quiz": "exercise",
    "external quiz": "exercise",
    "html activity": "exercise",
    "questionnaire": "exercise",
    "repeated activity": "exercise",
    "dataplus": "exercise",
    "interactive activity": "exercise",
    "forum": "interactive",
    "ouwiki": "interactive",
    "ouelluminate": "interactive",
    "glossary": "interactive",
    "workshop": "interactive",
    "choice": "interactive",
    "feedback": "interactive",
    "resource": "article",
    "oucontent": "article",
    "page": "article",
    "subpage": "article",
    "oubook": "article",
    "url": "article",
    "oupage": "article",
    "folder": "article",
    "sharedsubpage": "article",
    "dualpane": "article",
    "homepage": "article",
    "external tool": "article",
}
DEFAULT_RESOURCE_TYPE = "article"

# Nominal presentation start anchors (year -> calendar date for B/J presentations)
PRESENTATION_ANCHOR = {"B": (2, 3), "J": (10, 7)}

SESSION_EPOCH = datetime(2020, 1, 1)


def presentation_start(code_presentation: str) -> date:
    year = int(code_presentation[:4])
    month, day = PRESENTATION_ANCHOR[code_presentation[-1]]
    return date(year, month, day)


def real_date(code_presentation: str, days_since_start) -> date:
    base = presentation_start(code_presentation)
    if days_since_start in ("", None):
        return base
    return base + timedelta(days=int(float(days_since_start)))


def load_selected_students(raw_dir: pathlib.Path, limit: int) -> dict:
    """Pick `limit` students with completed presentations, retaining all their
    module-presentation rows."""
    students = defaultdict(list)
    with open(raw_dir / "studentInfo.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            students[int(row["id_student"])].append(row)
    # prefer students active in exactly one presentation for clean trajectories
    single = sorted([sid for sid, rows in students.items() if len(rows) == 1])
    selected_ids = set(single[:limit])
    return {sid: students[sid] for sid in selected_ids}


def main() -> int:
    parser = argparse.ArgumentParser(description="Map OULAD into CAREERMIND schema")
    parser.add_argument("--raw-dir", default="data/oulad/raw/")
    parser.add_argument("--uri", default="mongodb://localhost:27017")
    parser.add_argument("--db", default="careermind")
    parser.add_argument("--limit-students", type=int, default=200)
    parser.add_argument("--with-events", action="store_true",
                        help="also insert per-row VLE events (larger insert volume)")
    args = parser.parse_args()

    raw_dir = pathlib.Path(args.raw_dir)
    if not (raw_dir / "studentInfo.csv").exists():
        print("OULAD CSVs not found — run data/oulad/download.py first.")
        return 1

    try:
        from pymongo import MongoClient
    except ImportError:
        print("pymongo is required: pip install pymongo")
        return 1

    selected = load_selected_students(raw_dir, args.limit_students)
    print(f"Selected {len(selected)} OULAD students (single-presentation).")

    # --- grades: studentAssessment (all selected students) ---
    grades = defaultdict(list)
    with open(raw_dir / "studentAssessment.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            sid = int(row["id_student"])
            if sid in selected and row["score"] not in ("", None):
                grades[sid].append(
                    {
                        "assessment_id": row["id_assessment"],
                        "score": float(row["score"]),
                        "date_submitted": row["date_submitted"],
                    }
                )

    # --- assessment metadata (module per assessment) ---
    assessment_module = {}
    with open(raw_dir / "assessments.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            assessment_module[row["id_assessment"]] = (row["code_module"], row["code_presentation"], row["assessment_type"])

    # --- resources ---
    resources = {}
    with open(raw_dir / "vle.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            resources[(row["code_module"], row["code_presentation"], row["id_site"])] = {
                "external_id": row["id_site"],
                "module": row["code_module"],
                "presentation": row["code_presentation"],
                "activity_type": row["activity_type"],
                "type": ACTIVITY_TYPE_MAP.get(row["activity_type"].lower(), DEFAULT_RESOURCE_TYPE),
                "source": "oulad",
            }

    # --- sessions: one per (student, day) from studentVle (streamed, filtered) ---
    sessions = defaultdict(dict)  # sid -> {date_key: session dict}
    vle_rows = []
    with open(raw_dir / "studentVle.csv", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            sid = int(row["id_student"])
            if sid not in selected:
                continue
            d = real_date(row["code_presentation"], row["date"])
            key = d.isoformat()
            s = sessions[sid].setdefault(
                key,
                {
                    "student": f"oulad_{sid}",
                    "started_at": SESSION_EPOCH.replace(
                        year=d.year, month=d.month, day=d.day, hour=20
                    ),
                    "status": "completed",
                    "interaction_count": 0,
                    "resources_visited": 0,
                    "date": key,
                    "source": "oulad",
                },
            )
            s["interaction_count"] += int(row["sum_click"])
            s["resources_visited"] += 1
            if args.with_events:
                vle_rows.append(
                    {
                        "student": f"oulad_{sid}",
                        "session_date": key,
                        "type": "resource_open",
                        "resource_id": row["id_site"],
                        "metadata": {
                            "sum_click": int(row["sum_click"]),
                            "module": row["code_module"],
                            "presentation": row["code_presentation"],
                        },
                        "timestamp": s["started_at"],
                        "source": "oulad",
                    }
                )

    # --- write to MongoDB (idempotent: replace source=oulad docs) ---
    client = MongoClient(args.uri)
    db = client[args.db]

    db.profiles.delete_many({"source": "oulad"})
    db.sessions.delete_many({"source": "oulad"})
    db.events.delete_many({"source": "oulad"})
    db.resources.delete_many({"source": "oulad"})

    profile_docs = []
    for sid, rows in selected.items():
        info = rows[0]
        presentation = info["code_presentation"]
        academic_records = []
        for g in grades.get(sid, []):
            module, pres, atype = assessment_module.get(g["assessment_id"], (info["code_module"], presentation, ""))
            academic_records.append(
                {
                    "subject": f"{module} {atype}",
                    "grade": g["score"],
                    "semester": pres,
                    "graded_at": presentation_start(pres).isoformat(),
                }
            )
        profile_docs.append(
            {
                "email": f"oulad_{sid}@careermind.local",
                "full_name": f"OULAD Student {sid}",
                "external_id": str(sid),
                "programme": info["code_module"],
                "year_of_study": 3,
                "academic_records": academic_records,
                "final_results": [
                    {"module": r["code_module"], "presentation": r["code_presentation"], "result": r["final_result"]}
                    for r in rows
                ],
                "source": "oulad",
            }
        )
    if profile_docs:
        db.profiles.insert_many(profile_docs)

    session_docs = [s for per_student in sessions.values() for s in per_student.values()]
    if session_docs:
        db.sessions.insert_many(session_docs)

    if args.with_events and vle_rows:
        for i in range(0, len(vle_rows), 5000):
            db.events.insert_many(vle_rows[i : i + 5000])
    if resources:
        db.resources.insert_many(list(resources.values()))

    print(
        f"Mapped: {len(profile_docs)} profiles, {len(session_docs)} sessions, "
        f"{len(vle_rows) if args.with_events else 0} events, {len(resources)} resources "
        f"(source=oulad in db '{args.db}')"
    )
    print("Gaps (TCR/QAP/skills/career outcomes) are filled by the synthetic simulator.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
