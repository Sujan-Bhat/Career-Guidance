#!/usr/bin/env python
"""Seed MongoDB with the career knowledge graph (works today; Phase 1 extends it).

Loads data/knowledge_graph/careers_seed.json into the `career_pathways` and
`kg_skills` collections. Idempotent: replaces existing seed documents.

Usage:
    python data/seeds/seed_mongo.py [--uri mongodb://localhost:27017] [--db careermind]
"""
import argparse
import json
import pathlib
import sys

SEED_PATH = pathlib.Path(__file__).resolve().parent.parent / "knowledge_graph" / "careers_seed.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed CAREERMIND MongoDB")
    parser.add_argument("--uri", default="mongodb://localhost:27017")
    parser.add_argument("--db", default="careermind")
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

    skills_result = db.kg_skills.replace_one({"_seed": True}, {"_seed": True, "items": seed["skills"]}, upsert=True)
    pathways_result = db.career_pathways.delete_many({})
    if seed["careers"]:
        db.career_pathways.insert_many(seed["careers"])

    print(
        f"Seeded database '{args.db}': "
        f"{len(seed['skills'])} skills (upsert id={skills_result.upserted_id}), "
        f"{db.career_pathways.count_documents({})} career pathways "
        f"(deleted {pathways_result.deleted_count} old rows)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
