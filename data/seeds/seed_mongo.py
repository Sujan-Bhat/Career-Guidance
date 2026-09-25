#!/usr/bin/env python
"""Seed MongoDB with the career knowledge graph + synthetic students (Phase 1).

Loads data/knowledge_graph/careers_seed.json into `career_pathways` and
`kg_skills`, then generates `--students` synthetic students (latent-parameter
simulator, calibrated to OULAD marginals when available) with their sessions,
events, grades, and skill assessments. Idempotent: replaces existing seed docs.

Usage:
    python data/seeds/seed_mongo.py [--uri mongodb://localhost:27017] [--db careermind]
                                    [--students 200] [--sessions-per-student 12]
                                    [--seed 42] [--skip-students]
"""
import argparse
import json
import pathlib
import sys

SEED_PATH = pathlib.Path(__file__).resolve().parent.parent / "knowledge_graph" / "careers_seed.json"
SIMULATOR_DIR = pathlib.Path(__file__).resolve().parent.parent / "simulator"
OULAD_RAW_DIR = pathlib.Path(__file__).resolve().parent.parent / "oulad" / "raw"

sys.path.insert(0, str(SIMULATOR_DIR))
from simulator import StudentSimulator  # noqa: E402


def seed_knowledge_graph(db, seed: dict) -> None:
    db.kg_skills.replace_one({"_seed": True}, {"_seed": True, "items": seed["skills"]}, upsert=True)
    db.career_pathways.delete_many({})
    # map seed JSON schema -> CareerPathway mongoengine schema (external_id)
    pathways = [
        {
            "external_id": career["id"],
            "name": career["name"],
            "category": career["category"],
            "description": career.get("description", ""),
            "prerequisites": career["prerequisites"],
            "typical_courses": career.get("typical_courses", []),
        }
        for career in seed["careers"]
    ]
    if pathways:
        db.career_pathways.insert_many(pathways)
    print(f"  knowledge graph: {len(seed['skills'])} skills, {len(pathways)} career pathways")


def seed_students(db, n_students: int, sessions_per_student: int, rng_seed: int) -> None:
    calibration = StudentSimulator.calibrate_from_oulad(OULAD_RAW_DIR)
    sim = StudentSimulator(config={"oulad_calibration": calibration, "sessions_per_student": sessions_per_student}, seed=rng_seed)

    db.profiles.delete_many({"source": "simulator"})
    db.sessions.delete_many({"source": "simulator"})
    db.events.delete_many({"source": "simulator"})

    profile_docs, session_docs, event_docs = [], [], []
    for student in sim.generate_students(n_students):
        sessions = sim.generate_sessions(student, sessions_per_student)
        outcome = sim.generate_outcomes(student, sessions)

        profile_docs.append(
            {
                "email": f"{student['student_id']}@careermind.local",
                "full_name": f"Synthetic Student {student['student_id']}",
                "external_id": student["student_id"],
                "programme": "BE Computer Science",
                "year_of_study": 3,
                "academic_records": [
                    {"subject": subject, "grade": grade, "semester": "2025S"}
                    for subject, grade in outcome["grades"].items()
                ],
                "skill_assessments": [
                    {"skill": skill, "score": score}
                    for skill, score in outcome["skill_scores"].items()
                ],
                "career_preferences": [
                    {"category": cat, "weight": weight}
                    for cat, weight in sorted(student["domain_affinity"].items(), key=lambda kv: -kv[1])[:3]
                ],
                "latents": {
                    "ability": student["ability"],
                    "motivation": student["motivation"],
                    "focus_tendency": student["focus_tendency"],
                    "domain_affinity": student["domain_affinity"],
                },
                # ground-truth label for the career-prediction ensemble (Phase 5)
                "career_outcome": {
                    "category": outcome["career_category"],
                    "pathway_id": outcome["career_pathway_id"],
                },
                "source": "simulator",
            }
        )
        for session in sessions:
            session_docs.append({**session, "status": "completed", "source": "simulator"})
            event_docs.extend(sim.explode_events(session))

    if profile_docs:
        db.profiles.insert_many(profile_docs)
    if session_docs:
        db.sessions.insert_many(session_docs)
    for i in range(0, len(event_docs), 5000):
        db.events.insert_many(event_docs[i : i + 5000])

    print(
        f"  synthetic students: {len(profile_docs)} profiles, {len(session_docs)} sessions, "
        f"{len(event_docs)} events (calibration: {calibration})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed CAREERMIND MongoDB")
    parser.add_argument("--uri", default="mongodb://localhost:27017")
    parser.add_argument("--db", default="careermind")
    parser.add_argument("--students", type=int, default=200)
    parser.add_argument("--sessions-per-student", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42, help="Simulator RNG seed (deterministic)")
    parser.add_argument("--skip-students", action="store_true", help="Only seed the knowledge graph")
    args = parser.parse_args()

    try:
        from pymongo import MongoClient
    except ImportError:
        print("pymongo is required: pip install pymongo")
        return 1

    with open(SEED_PATH) as f:
        seed = json.load(f)

    client = MongoClient(args.uri)
    db = client[args.db]

    print(f"Seeding database '{args.db}':")
    seed_knowledge_graph(db, seed)
    if not args.skip_students:
        seed_students(db, args.students, args.sessions_per_student, args.seed)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
