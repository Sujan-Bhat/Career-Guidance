"""One-time cleanup: collapse duplicate Recommendation rows.

The pre-fix RecommendationListView inserted a fresh pending document on every
GET (fixed in commit 49cd40a, which now reuses rows in place), so one
student+item pair accumulated up to 11 rows and accept/reject decisions were
visually shadowed by the duplicates on the next page load.

This script reduces every (student, item_id) group — the exact lookup key the
list view uses — to a single row:

  1. If any row in the group carries a decision (accepted/rejected), keep the
     LATEST decided row and drop the rest. The decision is user state and
     cannot be regenerated; post-cleanup the list view surfaces it again
     instead of a shadowing pending duplicate.
  2. Otherwise keep the latest row that holds a cached LLM explanation (paid
     quota — regenerating costs a request), falling back to the latest row.
  3. If the kept row lacks an explanation but a dropped sibling has one, the
     explanation is carried over to the kept row (same item, so the text stays
     valid; provenance is refreshed by the list view on the next GET anyway).

Dry-run by default; pass --apply to write. Idempotent: a second run is a no-op.

Usage (inside the web container, which has pymongo and the MONGO_* env):
    python /tmp/dedupe_recommendations.py           # dry-run, prints the plan
    python /tmp/dedupe_recommendations.py --apply   # execute the plan
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from pymongo import MongoClient

DECIDED = ("accepted", "rejected")


def _sort_key(row: dict) -> tuple:
    """Latest-first ordering; created_at is always set by the view, but treat a
    missing value as epoch and break exact ties with the ObjectId timestamp."""
    created = row.get("created_at") or datetime.fromtimestamp(0)
    return (created, row["_id"])


def choose_keeper(rows: list[dict]) -> tuple[dict, list[dict]]:
    """Return (keeper, drops) for one (student, item_id) group."""
    ordered = sorted(rows, key=_sort_key, reverse=True)
    decided = [r for r in ordered if r.get("decision") in DECIDED]
    if decided:
        keeper = decided[0]
    else:
        explained = [r for r in ordered if r.get("explanation")]
        keeper = (explained or ordered)[0]
    return keeper, [r for r in rows if r["_id"] != keeper["_id"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply", action="store_true", help="delete the duplicates (default: dry-run)"
    )
    parser.add_argument("--uri", default=os.getenv("MONGO_URI", "mongodb://mongo:27017"))
    parser.add_argument("--db", default=os.getenv("MONGO_DB_NAME", "careermind"))
    args = parser.parse_args()

    collection = MongoClient(args.uri)[args.db]["recommendation"]
    rows = list(collection.find({}))
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["student"], row["item_id"]), []).append(row)

    plan: list[tuple[dict, list[dict]]] = []
    for key in sorted(groups):
        keeper, drops = choose_keeper(groups[key])
        if drops:
            plan.append((keeper, drops))

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] {len(rows)} rows in {len(groups)} (student, item_id) groups")

    carried = 0
    for keeper, drops in plan:
        carry = next(
            (d.get("explanation") for d in drops if d.get("explanation")), None
        )
        note = ""
        if carry and not keeper.get("explanation"):
            carried += 1
            note = "  + carry explanation onto keeper"
        print(
            f"  student={keeper['student'][:12]}… item={keeper['item_id']:<6}"
            f" keep {_sort_key(keeper)[0]:%Y-%m-%d %H:%M:%S}"
            f" decision={keeper.get('decision')}"
            f" explained={bool(keeper.get('explanation'))}"
            f"  -> delete {len(drops)}{note}"
        )
        if args.apply and carry and not keeper.get("explanation"):
            collection.update_one({"_id": keeper["_id"]}, {"$set": {"explanation": carry}})

    delete_ids = [d["_id"] for _, drops in plan for d in drops]
    print(
        f"[{mode}] groups collapsed: {len(plan)}  rows to delete: {len(delete_ids)}"
        f"  rows after: {len(rows) - len(delete_ids)}"
        f"  explanations carried over: {carried}"
    )

    if not args.apply:
        print("[dry-run] nothing written — re-run with --apply to execute")
        return 0

    if delete_ids:
        result = collection.delete_many({"_id": {"$in": delete_ids}})
        print(f"[apply] deleted {result.deleted_count} rows")

    dupe_groups = list(
        collection.aggregate(
            [
                {"$group": {"_id": {"s": "$student", "i": "$item_id"}, "n": {"$sum": 1}}},
                {"$match": {"n": {"$gt": 1}}},
            ]
        )
    )
    remaining_dupes = len(dupe_groups)
    print(
        f"[verify] total rows now: {collection.count_documents({})}"
        f"  duplicate groups remaining: {remaining_dupes}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
