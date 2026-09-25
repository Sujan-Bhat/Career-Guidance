"""Stage 1: knowledge-based candidate generation (paper Sec. V-B).

Career-domain knowledge graph: career categories as nodes, prerequisite
skill requirements as directed edges [24]. Candidates are eligible when the
student meets at least 60% of prerequisites — cold-start resilient.
"""
import json
import pathlib
from typing import Optional

import networkx as nx

DEFAULT_ELIGIBILITY_THRESHOLD = 0.60
SEED_PATH = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_graph" / "careers_seed.json"


def load_knowledge_graph(seed_path: str | pathlib.Path = SEED_PATH) -> nx.DiGraph:
    """Load careers_seed.json into a directed graph.

    Nodes: career categories (attr: `kind="career"`, name, category,
    description, prerequisites, typical_courses) and skills
    (attr: `kind="skill"`, label).
    Edges: skill -> career, weighted by min_level (attr: `min_level`).
    """
    with open(seed_path) as fh:
        seed = json.load(fh)

    graph = nx.DiGraph()
    for skill in seed["skills"]:
        graph.add_node(skill["id"], kind="skill", label=skill["name"])
    for career in seed["careers"]:
        graph.add_node(
            career["id"],
            kind="career",
            label=career["name"],
            category=career["category"],
            description=career.get("description", ""),
            prerequisites=career["prerequisites"],
            typical_courses=career.get("typical_courses", []),
        )
        for prereq in career["prerequisites"]:
            graph.add_edge(prereq["skill"], career["id"], min_level=prereq["min_level"])
    return graph


def get_careers(graph: nx.DiGraph) -> list[dict]:
    """All career nodes with their attributes (id first)."""
    careers = []
    for node, data in graph.nodes(data=True):
        if data.get("kind") == "career":
            careers.append({"id": node, **data})
    return careers


def prerequisite_eligibility(student_skills: dict, career_prerequisites: list) -> float:
    """Fraction (0..1) of a career's prerequisites met by the student.

    A prerequisite is met when the student's skill level (1-5) is at or above
    the career's min_level. Missing skills count as unmet.
    """
    if not career_prerequisites:
        return 1.0
    met = sum(
        1
        for prereq in career_prerequisites
        if student_skills.get(prereq["skill"], 0) >= prereq["min_level"]
    )
    return met / len(career_prerequisites)


def generate_candidates(
    student_skills: dict,
    graph: nx.DiGraph,
    threshold: float = DEFAULT_ELIGIBILITY_THRESHOLD,
) -> list[dict]:
    """Stage 1: all careers whose eligibility fraction >= threshold,
    ordered by eligibility (desc) then career id."""
    candidates = []
    for career in get_careers(graph):
        eligibility = prerequisite_eligibility(student_skills, career["prerequisites"])
        if eligibility >= threshold:
            candidates.append(
                {
                    "id": career["id"],
                    "name": career["label"],
                    "category": career["category"],
                    "eligibility": round(eligibility, 4),
                    "prerequisites_met": f"{eligibility * len(career['prerequisites']):.0f}/{len(career['prerequisites'])}",
                }
            )
    candidates.sort(key=lambda c: (-c["eligibility"], c["id"]))
    return candidates
