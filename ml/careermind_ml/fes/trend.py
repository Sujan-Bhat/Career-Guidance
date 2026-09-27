"""FES trajectory helper (current + 14-day trend) shared by feature builders.

History is short for new users (2-7 sessions): the comparison window would be
empty and np.mean([]) yields NaN, which downstream models (sklearn trees)
reject. This helper returns a neutral 0.5 trend until enough history exists.
"""
import numpy as np


def compute_fes_trend(series: list[tuple]) -> float | None:
    """Normalised trend from a (timestamp, fes) series sorted ascending.

    Returns None when there is no series (< 2 rows), 0.5 when the prior
    window is empty (fewer than 8 rows), else the clipped Eq.-1 trajectory
    used across the platform.
    """
    if len(series) < 2:
        return None
    recent = [f for _, f in series[-7:]]
    previous = [f for _, f in series[-14:-7]] or [f for _, f in series[:-7]]
    if not previous:
        return 0.5  # too short for a comparison window — neutral trend
    return float(np.clip(0.5 + (np.mean(recent) - np.mean(previous)) / 2.0, 0.0, 1.0))
