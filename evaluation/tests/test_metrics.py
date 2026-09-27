"""Ranking-metric tests (paper Sec. VIII)."""
import pytest

from metrics import ndcg_at_k, precision_at_k, recall_at_k


def test_precision_recall_basic():
    recommended = ["a", "b", "c", "d"]
    relevant = {"a", "c", "z"}
    assert precision_at_k(recommended, relevant, k=4) == pytest.approx(2 / 4)
    assert recall_at_k(recommended, relevant, k=4) == pytest.approx(2 / 3)


def test_metrics_respect_k():
    recommended = ["a", "b", "c"]
    relevant = {"c"}
    assert precision_at_k(recommended, relevant, k=2) == 0.0
    assert recall_at_k(recommended, relevant, k=2) == 0.0
    assert ndcg_at_k(recommended, relevant, k=3) > ndcg_at_k(recommended, relevant, k=2)


def test_ndcg_perfect_and_empty():
    recommended = ["a", "b", "c"]
    assert ndcg_at_k(recommended, {"a", "b", "c"}, k=3) == pytest.approx(1.0)
    assert ndcg_at_k(recommended, set(), k=3) == 0.0
    assert recall_at_k(recommended, set(), k=3) == 0.0  # no relevant -> 0 by convention


def test_k_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        precision_at_k(["a"], {"a"}, k=0)


def test_hit_later_positions_discounted_but_counted():
    recommended = ["x", "y", "z", "a"]
    # ndcg > 0 whenever a relevant item appears within k
    assert ndcg_at_k(recommended, {"a"}, k=4) > 0
    assert ndcg_at_k(recommended, {"a"}, k=3) == 0
