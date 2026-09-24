"""Training features for the career path predictor (paper Sec. V-D).

Feature groups:
  * cumulative academic performance
  * skill-domain strength
  * experiential-learning participation
  * FES trajectory (current + 14-day trend)
  * stated career preferences
"""
import pandas as pd


def build_feature_frame(profiles, fes_history, career_preferences) -> pd.DataFrame:
    """Phase 5: assemble the model feature matrix from Mongo collections."""
    raise NotImplementedError("Phase 5")
