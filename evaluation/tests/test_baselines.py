"""Single-technique baseline tests (paper Sec. VIII) — no Mongo required."""
import pytest

from baselines import SingleTechniqueBaseline, popularity_ranking
from careermind_ml.recommender.cf import item_cooccurrence
from careermind_ml.recommender.knowledge_graph import load_knowledge_graph

CANDIDATES = ["c01", "c02", "c03", "c04", "c05", "c06"]


@pytest.fixture(scope="module")
def graph():
    return load_knowledge_graph()


def test_unknown_technique_rejected():
    with pytest.raises(ValueError, match="Unknown baseline"):
        SingleTechniqueBaseline("not-a-technique")


def test_missing_context_rejected():
    with pytest.raises(ValueError, match="requires the knowledge graph"):
        SingleTechniqueBaseline("kg_only")
    with pytest.raises(ValueError, match="co-occurrence"):
        SingleTechniqueBaseline("cf_only")
    with pytest.raises(ValueError, match="FM"):
        SingleTechniqueBaseline("fm_only")


def test_kg_only_full_ordering_by_eligibility(graph):
    baseline = SingleTechniqueBaseline("kg_only", graph=graph)
    ranking = baseline.rank({"skills": {}}, CANDIDATES)
    assert sorted(ranking) == sorted(CANDIDATES)
    # deterministic
    assert ranking == baseline.rank({"skills": {}}, CANDIDATES)


def test_cf_only_orders_by_affinity():
    interactions = [
        {"student": "s1", "item_id": "c01", "session": "s1:0", "date": "2025-01-01"},
        {"student": "s1", "item_id": "c02", "session": "s1:0", "date": "2025-01-01"},
        {"student": "s2", "item_id": "c01", "session": "s2:0", "date": "2025-01-02"},
        {"student": "s2", "item_id": "c03", "session": "s2:0", "date": "2025-01-02"},
        {"student": "s3", "item_id": "c02", "session": "s3:0", "date": "2025-01-03"},
        {"student": "s3", "item_id": "c03", "session": "s3:0", "date": "2025-01-03"},
    ]
    cooc = item_cooccurrence(interactions, {})
    baseline = SingleTechniqueBaseline("cf_only", cooc=cooc)
    ranking = baseline.rank({"history": ["c01"]}, ["c01", "c02", "c03", "c04"])
    # c02 co-occurs with c01; c04 never appears -> last
    assert ranking.index("c02") < ranking.index("c04")


def test_popularity_orders_by_fes_weighted_frequency():
    interactions = [
        {"student": "s1", "item_id": "c03", "session": "s1:0"},
        {"student": "s2", "item_id": "c03", "session": "s2:0"},
        {"student": "s3", "item_id": "c01", "session": "s3:0"},
    ]
    # c03 seen twice (weight .5+.5=1.0), c01 once (weight 1.0) -> tie broken by id
    ranking = popularity_ranking(interactions, ["c01", "c02", "c03"])
    assert ranking[0] in ("c01", "c03")
    assert ranking[-1] == "c02"  # never interacted

    # FES weighting breaks the tie toward the higher-FES session
    ranking = popularity_ranking(interactions, ["c01", "c03"], {"s1:0": 1.0, "s2:0": 1.0, "s3:0": 0.1})
    assert ranking[0] == "c03"
    assert ranking[1] == "c01"


def test_fm_only_returns_full_ranking():
    torch = pytest.importorskip("torch", reason="torch not installed")
    from careermind_ml.recommender.fm import FactorizationMachine
    from careermind_ml.recommender.features import GRADE_SUBJECTS, FeatureSpec

    spec = FeatureSpec(
        item_vocab=CANDIDATES,
        population_grades={subject: 50.0 for subject in GRADE_SUBJECTS},
    )
    model = FactorizationMachine(spec.dim, k=4)
    model.eval()
    baseline = SingleTechniqueBaseline("fm_only", fm_model=model, fm_spec=spec)
    agg = {"grades": {}, "fes_current": None, "fes_trend": None, "preferences": {}, "year_of_study": 3}
    ranking = baseline.rank({"agg": agg}, CANDIDATES)
    assert sorted(ranking) == sorted(CANDIDATES)
    assert ranking == baseline.rank({"agg": agg}, CANDIDATES)  # deterministic
