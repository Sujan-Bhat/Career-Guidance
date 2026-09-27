"""Feature attribution for prediction transparency (paper Sec. V-D).

Displays the top contributing profile features alongside each prediction,
consistent with the design validation of Pordelan and Hosseinian [30] and
agency-preserving guidance [26].

Method: per-prediction occlusion importance — for each feature, replace it
with its population default (the value a brand-new user would have), re-run
the ensemble, and measure how the probability of the predicted category
drops. Positive importance = the feature pushed the model toward this
prediction. Model-agnostic and dependency-free (SHAP rejected: heavy).
"""
import pandas as pd


def top_contributing_features(
    model,
    X: pd.DataFrame,
    prediction: str,
    k: int = 5,
    baseline: dict | None = None,
) -> list:
    """Per-prediction occlusion importance over the ensemble for ONE student.

    `X` is the single-row feature frame behind `prediction`; `baseline` is the
    artifact's population defaults (column -> value). Returns the top-k
    [{"feature": name, "importance": delta}, ...] sorted by |importance|.
    """
    baseline = baseline or {}
    row = X.iloc[[0]]
    proba = model.predict_proba(row)[0]
    classes = list(model.classes_)
    if prediction not in classes:
        return []
    target = classes.index(prediction)
    base_p = float(proba[target])

    importances = []
    for column in X.columns:
        occluded = row.copy()
        occluded[column] = baseline.get(column, 0.0)
        p = float(model.predict_proba(occluded)[0][target])
        importances.append({"feature": column, "importance": base_p - p})

    importances.sort(key=lambda item: abs(item["importance"]), reverse=True)
    return importances[:k]
