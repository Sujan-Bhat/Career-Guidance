"""Stage 2: collaborative re-ranking (paper Sec. V-B).

Item-to-item collaborative filtering [32] over course/pathway co-occurrence,
using the implicit-feedback framework of Koren et al. [2]: each session's
contribution to the CF score is weighted by its FES value, so higher-focus
sessions carry more influence.
"""

DEFAULT_FES_FOR_MISSING_SESSION = 0.5  # neutral weight when FES is unknown


def _interaction_weight(interaction: dict, fes_by_session: dict) -> float:
    fes = fes_by_session.get(interaction.get("session"))
    if fes is None:
        fes = DEFAULT_FES_FOR_MISSING_SESSION
    return max(0.0, min(1.0, float(fes)))


def item_cooccurrence(interactions: list[dict], fes_by_session: dict | None = None) -> dict:
    """Build FES-weighted item-to-item co-occurrence.

    For every student, each ordered pair of engaged items contributes
    w_i * w_j, where w is the FES of the session the item was engaged in
    (Koren-style implicit confidence). Popularity-normalised afterwards
    (cosine-like), so popular items don't dominate affinity scores.

    Returns: {item_a: {item_b: affinity}} (symmetric).
    """
    fes_by_session = fes_by_session or {}
    by_student: dict[str, list[dict]] = {}
    for interaction in interactions:
        by_student.setdefault(interaction["student"], []).append(interaction)

    raw: dict[str, dict[str, float]] = {}
    popularity: dict[str, float] = {}
    for student_items in by_student.values():
        for ia in student_items:
            item_a = ia["item_id"]
            w_a = _interaction_weight(ia, fes_by_session)
            popularity[item_a] = popularity.get(item_a, 0.0) + w_a
            for ib in student_items:
                item_b = ib["item_id"]
                if item_b == item_a:
                    continue
                w_b = _interaction_weight(ib, fes_by_session)
                raw.setdefault(item_a, {})
                raw[item_a][item_b] = raw[item_a].get(item_b, 0.0) + w_a * w_b

    # popularity (cosine) normalisation
    cooc: dict[str, dict[str, float]] = {}
    for item_a, neighbours in raw.items():
        norm_a = popularity.get(item_a, 0.0) ** 0.5
        cooc[item_a] = {}
        for item_b, weight in neighbours.items():
            norm_b = popularity.get(item_b, 0.0) ** 0.5
            denom = norm_a * norm_b
            cooc[item_a][item_b] = weight / denom if denom > 0 else 0.0
    return cooc


def cf_score(candidate_id: str, cooc: dict, student_items: list[str]) -> float:
    """Affinity of a candidate item to the student's engagement history."""
    return sum(cooc.get(candidate_id, {}).get(item, 0.0) for item in student_items)


def student_history_items(interactions: list[dict], student: str) -> list[str]:
    """Items the student has engaged with (distinct)."""
    return list({i["item_id"] for i in interactions if i["student"] == student})


def cf_rerank(candidates: list[dict], cooc: dict, student_items: list[str]) -> list[dict]:
    """Re-rank Stage-1 candidates by FES-weighted CF affinity.

    Adds `stage2_cf_score` to each candidate and re-orders by it (descending).
    """
    scored = [
        {**candidate, "stage2_cf_score": cf_score(candidate["id"], cooc, student_items)}
        for candidate in candidates
    ]
    scored.sort(key=lambda c: (-c["stage2_cf_score"], c["id"]))
    return scored
