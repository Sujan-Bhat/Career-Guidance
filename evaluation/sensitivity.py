"""Sensitivity analysis of unvalidated design thresholds (paper Sec. VII #4).

Parameters to sweep in the pilot study:
  * stage1_eligibility_threshold      (default 0.60)
  * engagement_signal.min_session_minutes (default 15)
  * engagement_signal.min_interactions_per_min (default 3)
  * engagement_signal.min_quiz_attempt_rate (default 0.6)
  * weight_calibration.min_sessions (default 8)
  * weight_calibration.min_graded_outcomes (default 2)
  * weight_calibration.min_nonmissing_per_submetric (default 3)
  * reward_weights alpha/beta/gamma/delta (Eq. 3)
"""

DEFAULTS = {
    "stage1_eligibility_threshold": 0.60,
    "min_session_minutes": 15,
    "min_interactions_per_min": 3,
    "min_quiz_attempt_rate": 0.6,
    "min_sessions": 8,
    "min_graded_outcomes": 2,
    "min_nonmissing_per_submetric": 3,
}


def sweep(parameter: str, values: list) -> dict:
    """Phase 9: re-run the relevant pipeline component across `values`,
    record metric deltas, return {value: {metric: score}}."""
    raise NotImplementedError("Phase 9")
