"""FES trend helper tests — short-history NaN regression (Phase 5 fix)."""
import pytest

from careermind_ml.fes.trend import compute_fes_trend


def test_no_series_returns_none():
    assert compute_fes_trend([]) is None
    assert compute_fes_trend([("t", 0.5)]) is None


def test_short_history_neutral_not_nan():
    # 2..7 rows: the old inline math did np.mean([]) -> NaN, which sklearn
    # tree ensembles reject at inference time
    for n in range(2, 8):
        series = [(f"t{i}", 0.6) for i in range(n)]
        trend = compute_fes_trend(series)
        assert trend == 0.5
        assert trend == trend  # not NaN


def test_long_history_uses_comparison_window():
    # 20 rows: comparison window = rows 6..12, recent = rows 13..19
    rising = [(f"t{i}", 0.3) for i in range(13)] + [(f"t{i}", 0.9) for i in range(13, 20)]
    assert compute_fes_trend(rising) > 0.5  # improving engagement
    falling = [(f"t{i}", 0.9) for i in range(13)] + [(f"t{i}", 0.3) for i in range(13, 20)]
    assert compute_fes_trend(falling) < 0.5  # declining engagement
    assert 0.0 <= compute_fes_trend(rising) <= 1.0


def test_flat_history_stays_neutral():
    flat = [(f"t{i}", 0.6) for i in range(14)]
    assert compute_fes_trend(flat) == pytest.approx(0.5)
