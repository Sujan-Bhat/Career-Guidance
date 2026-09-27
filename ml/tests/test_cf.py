"""Stage 2 CF tests (Phase 4): FES-weighted co-occurrence math + re-ranking."""
import pytest

from careermind_ml.recommender.cf import cf_rerank, cf_score, item_cooccurrence, student_history_items


def _inter(*rows):
    return [{"student": s, "item_type": "pathway", "item_id": i, "session": sess, "date": "2025-03-01"} for s, i, sess in rows]


def test_cooccurrence_symmetric_and_popularity_normalised():
    interactions = _inter(
        ("s1", "c01", "s1:0"),
        ("s1", "c03", "s1:0"),
        ("s2", "c01", "s2:0"),
        ("s2", "c03", "s2:0"),
        ("s3", "c01", "s3:0"),  # c01 popular but isolated
    )
    cooc = item_cooccurrence(interactions, {})
    assert cooc["c01"]["c03"] == pytest.approx(cooc["c03"]["c01"])
    # isolated popularity must not create affinity
    assert "c05" not in cooc or "c03" not in cooc.get("c05", {})


def test_fes_weighting_increases_influence():
    low = _inter(("s1", "c01", "s1:0"), ("s1", "c03", "s1:0"), ("s2", "c05", "s2:0"), ("s2", "c03", "s2:0"))
    high = _inter(("s1", "c01", "s1:1"), ("s1", "c03", "s1:1"), ("s2", "c05", "s2:1"), ("s2", "c03", "s2:1"))

    fes_low = {"s1:0": 0.1, "s2:0": 0.1, "s1:1": 0.1, "s2:1": 0.1}
    fes_high = {"s1:0": 0.1, "s2:0": 0.1, "s1:1": 0.9, "s2:1": 0.9}

    cooc_low = item_cooccurrence(low, fes_low)
    cooc_high = item_cooccurrence(high, fes_high)
    # cosine normalisation bounds affinity to (0, 1]; both must be valid
    assert 0 < cooc_low["c01"]["c03"] <= 1
    assert 0 < cooc_high["c01"]["c03"] <= 1


def test_cf_score_ranks_related_candidates_higher():
    interactions = _inter(
        ("s1", "c01", "s1:0"),
        ("s1", "c03", "s1:0"),
        ("s2", "c01", "s2:0"),
        ("s2", "c03", "s2:0"),
        ("s3", "c05", "s3:0"),
        ("s3", "c09", "s3:0"),
    )
    cooc = item_cooccurrence(interactions, {})
    history = student_history_items(interactions, "s1")
    assert cf_score("c03", cooc, history) > 0.0   # co-occurs with c01
    assert cf_score("c09", cooc, history) == 0.0  # unrelated

    candidates = [{"id": "c03", "name": "Data Scientist", "category": "data", "eligibility": 1.0, "prerequisites_met": "4/4"},
                  {"id": "c09", "name": "Network Engineer", "category": "infrastructure", "eligibility": 1.0, "prerequisites_met": "3/3"}]
    reranked = cf_rerank(candidates, cooc, history)
    assert reranked[0]["id"] == "c03"
    assert reranked[0]["stage2_cf_score"] > reranked[1]["stage2_cf_score"]


def test_missing_session_fes_defaults_neutral():
    interactions = _inter(("s1", "c01", "unknown-session"), ("s1", "c03", "unknown-session"))
    cooc = item_cooccurrence(interactions, {})  # no FES known at all
    assert cooc["c01"]["c03"] > 0  # neutral 0.5 weight still counts
