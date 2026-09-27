"""Sensitivity-sweep tests — custom runner, no Mongo (paper Sec. VIII #4)."""
import pytest

import sensitivity


def test_sweep_uses_custom_run_callback():
    seen = []

    def run(value):
        seen.append(value)
        return {"metric": value * 2}

    result = sensitivity.sweep("stage1_eligibility_threshold", [0.4, 0.6, 0.8], run=run)
    assert seen == [0.4, 0.6, 0.8]
    assert result[0.6] == {"metric": 1.2}


def test_sweep_stringifies_unhashable_values():
    result = sensitivity.sweep(
        "reward_weights",
        [{"alpha": 0.4, "beta": 0.3, "gamma": 0.1, "delta": 0.2}],
        run=lambda weights: {"mean_reward": weights["alpha"]},
    )
    assert len(result) == 1
    (key, row), = result.items()
    assert "alpha" in key  # dict value became a JSON string key
    assert row == {"mean_reward": 0.4}


def test_sweep_rejects_unknown_parameter():
    with pytest.raises(ValueError, match="Unknown parameter"):
        sensitivity.sweep("not_a_parameter", [1], run=lambda v: {})


def test_every_family_has_a_default_runner():
    for parameter in sensitivity.FAMILY:
        runner = sensitivity._default_runner(parameter)
        assert callable(runner)


def test_default_grids_cover_all_families():
    grids = sensitivity.default_grids()
    assert {"stage1_eligibility_threshold", "min_session_minutes", "min_sessions", "reward_weights"} <= set(grids)
    assert 0.60 in grids["stage1_eligibility_threshold"]  # paper default included


def test_engagement_threshold_override_changes_signal():
    from careermind_ml.fes.engagement import engagement_signal

    # 12-minute session: fails the paper's 15-min rule but passes a 10-min gate
    assert engagement_signal(12, interaction_count=60, quiz_attempt_rate=1.0) == 0
    assert engagement_signal(12, interaction_count=60, quiz_attempt_rate=1.0, min_session_minutes=10) == 1
