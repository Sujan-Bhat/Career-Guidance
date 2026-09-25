"""Knowledge-graph loader validation (Phase 1)."""
import pytest

from careermind_ml.recommender.knowledge_graph import (
    DEFAULT_ELIGIBILITY_THRESHOLD,
    generate_candidates,
    get_careers,
    load_knowledge_graph,
    prerequisite_eligibility,
)


@pytest.fixture(scope="module")
def graph():
    return load_knowledge_graph()


def test_graph_structure(graph):
    careers = get_careers(graph)
    assert len(careers) == 18
    assert graph.number_of_nodes() == 18 + 20  # careers + skills
    # every career has at least one skill->career prerequisite edge
    for career in careers:
        assert career["prerequisites"], f"{career['id']} has no prerequisites"
        for prereq in career["prerequisites"]:
            assert graph.has_edge(prereq["skill"], career["id"])


def test_eligibility_math():
    prereqs = [{"skill": "a", "min_level": 3}, {"skill": "b", "min_level": 4}, {"skill": "c", "min_level": 5}]
    # meets 2 of 3
    assert prerequisite_eligibility({"a": 3, "b": 4, "c": 1}, prereqs) == pytest.approx(2 / 3)
    # level below min_level does not count
    assert prerequisite_eligibility({"a": 2, "b": 4, "c": 5}, prereqs) == pytest.approx(2 / 3)
    # missing skills count as unmet
    assert prerequisite_eligibility({}, prereqs) == 0.0
    assert prerequisite_eligibility({"a": 5, "b": 5, "c": 5}, prereqs) == 1.0


def test_candidate_generation_threshold(graph):
    strong = {
        "dsa": 5, "programming_python": 5, "programming_java": 4, "statistics": 5,
        "ml_fundamentals": 4, "databases_sql": 4, "web_backend": 3, "softeng_practices": 4,
        "operating_systems": 3, "javascript_ts": 3, "web_frontend": 3, "cloud_platforms": 2,
    }
    candidates = generate_candidates(strong, graph)
    assert candidates, "strong student should match at least one career"
    assert all(c["eligibility"] >= DEFAULT_ELIGIBILITY_THRESHOLD for c in candidates)
    # sorted by eligibility desc
    eligs = [c["eligibility"] for c in candidates]
    assert eligs == sorted(eligs, reverse=True)
    # the strong software/data profile qualifies for Software Engineer fully
    top = {c["id"]: c for c in candidates}
    assert top["c01"]["eligibility"] == 1.0

    # a student with no skills is cold-start: nothing eligible via KG alone
    assert generate_candidates({}, graph) == []


def test_partial_eligibility_still_passes_threshold(graph):
    """Data Scientist (c03) needs 4 prereqs; meeting 3/4 = 0.75 >= 0.60."""
    partial = {"programming_python": 3, "ml_fundamentals": 3, "databases_sql": 3}  # statistics=4 missing
    candidates = {c["id"]: c for c in generate_candidates(partial, graph)}
    assert "c03" in candidates
    assert candidates["c03"]["eligibility"] == pytest.approx(0.75)
