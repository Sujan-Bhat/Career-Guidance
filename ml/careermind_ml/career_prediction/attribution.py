"""Feature attribution for prediction transparency (paper Sec. V-D).

Displays the top contributing profile features alongside each prediction,
consistent with the design validation of Pordelan and Hosseinian [30] and
agency-preserving guidance [26].
"""
import pandas as pd


def top_contributing_features(model, X: pd.DataFrame, prediction, k: int = 5) -> list:
    """Phase 5: permutation importance over the ensemble for one prediction.
    Returns [{"feature": name, "importance": value}, ...] (top k)."""
    raise NotImplementedError("Phase 5")
