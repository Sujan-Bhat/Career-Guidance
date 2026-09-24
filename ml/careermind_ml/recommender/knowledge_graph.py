"""Stage 1: knowledge-based candidate generation (paper Sec. V-B).

Career-domain knowledge graph: career categories as nodes, prerequisite
skill requirements as directed edges [24]. Candidates are eligible when the
student meets at least 60% of prerequisites — cold-start resilient.
"""
import networkx as nx

DEFAULT_ELIGIBILITY_THRESHOLD = 0.60


def load_knowledge_graph(seed_path: str) -> nx.DiGraph:
    """Load careers_seed.json into a directed graph.

    Nodes: career categories (with prerequisite attributes) and skills.
    Edges: skill -> career, weighted by min_level.
    """
    raise NotImplementedError("Phase 4")


def prerequisite_eligibility(student_skills: dict, career_prerequisites: list) -> float:
    """Fraction (0..1) of prerequisites met by the student."""
    raise NotImplementedError("Phase 4")


def generate_candidates(student_skills: dict, graph: nx.DiGraph, threshold: float = DEFAULT_ELIGIBILITY_THRESHOLD) -> list:
    """Stage 1: all careers whose eligibility fraction >= threshold."""
    raise NotImplementedError("Phase 4")
