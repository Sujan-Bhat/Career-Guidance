"""Career prediction ensemble tests (Phase 5): features, stacking, attribution."""
import numpy as np
import pandas as pd
import pytest

from careermind_ml.career_prediction.attribution import top_contributing_features
from careermind_ml.career_prediction.ensemble import (
    ARTIFACTS_DIR,
    build_ensemble,
    train_ensemble,
)
from careermind_ml.career_prediction.features import (
    ALL_COLUMNS,
    BASE_COLUMNS,
    PREFERENCE_COLUMNS,
    build_feature_frame,
    feature_row,
    load_skill_categories,
)

CATEGORIES = ("software", "data", "infrastructure", "security", "hardware", "management")

FAST_CONFIG = {
    "cv_folds": 3,
    "test_size": 0.2,
    "random_state": 0,
    "include_preferences": True,
    "random_forest": {"n_estimators": 30},
    "gradient_boosting": {"n_estimators": 30},
    "mlp": {"hidden_layer_sizes": [8], "max_iter": 60, "early_stopping": True},
}


def _make_students(n_per_class: int = 20, seed: int = 0) -> list[dict]:
    """Synthetic labelled population: per-category skills + one-hot prefs."""
    rng = np.random.default_rng(seed)
    mapping = load_skill_categories()
    cat_skills = {c: sorted(s for s, cats in mapping.items() if c in cats) for c in CATEGORIES}
    students = []
    for label in CATEGORIES:
        for i in range(n_per_class):
            pool = cat_skills[label]
            skills = {s: float(rng.integers(1, 6)) for s in rng.choice(pool, size=3, replace=False)}
            students.append(
                {
                    "student": f"{label}_{i:02d}",
                    "grades": {"CS201": 70.0, "CS230": 65.0, "CS320": 60.0, "ST210": 55.0, "CS350": 60.0},
                    "skills": skills,
                    "participation": {
                        "exp_sessions": 12,
                        "exp_interactions": 20,
                        "exp_distinct_items": 10,
                        "exp_mean_duration": 45.0,
                    },
                    "fes_current": 0.6,
                    "fes_trend": 0.5,
                    "preferences": {c: (0.9 if c == label else 0.02) for c in CATEGORIES},
                    "year_of_study": 3,
                    "label": label,
                }
            )
    return students


def test_skill_category_mapping_covers_all_categories():
    mapping = load_skill_categories()
    assert len(mapping) == 20  # every KG skill maps somewhere
    covered = set().union(*mapping.values())
    assert covered == set(CATEGORIES)


def test_feature_frame_shape_ranges_and_no_label_columns():
    students = _make_students(5)
    frame, defaults = build_feature_frame(students, include_preferences=True)
    assert frame.shape == (30, len(ALL_COLUMNS))
    assert list(frame.columns) == list(ALL_COLUMNS)
    assert not frame.isna().any().any()
    assert set(defaults) == set(ALL_COLUMNS)

    # leakage guard: the frame may only contain declared profile features
    assert not set(frame.columns) & {"career_outcome", "domain_affinity", "label", "pathway_id"}

    for column in ("grade_CS201", "fes_current", "fes_trend", "year"):
        assert frame[column].between(0.0, 1.0).all()
    for column in PREFERENCE_COLUMNS:
        assert frame[column].between(0.0, 1.0).all()
    assert np.allclose(frame[list(PREFERENCE_COLUMNS)].sum(axis=1), 1.0)  # normalised
    for column in ("skill_count_software", "skill_level_data"):
        assert frame[column].between(-1.0, 1.0).all()


def test_frame_regimes_and_split_alignment():
    students = _make_students(5)
    full, defaults = build_feature_frame(students, include_preferences=True)
    ablated, _ = build_feature_frame(students, include_preferences=False, population_defaults=defaults)
    assert list(ablated.columns) == list(BASE_COLUMNS)
    # train_ensemble splits by index: rows must stay aligned across regimes
    assert len(ablated) == len(full)
    for column in BASE_COLUMNS:
        assert np.allclose(full[column].values, ablated[column].values)


def test_cold_start_falls_back_to_population_and_uniform_prefs():
    students = _make_students(5)
    _, defaults = build_feature_frame(students, include_preferences=True)
    row = feature_row({}, load_skill_categories(), True, defaults)
    assert row["grade_CS201"] == defaults["grade_CS201"]
    assert row["fes_current"] == defaults["fes_current"]
    for column in PREFERENCE_COLUMNS:
        assert row[column] == pytest.approx(1.0 / 6)  # unstated -> uniform
    # no skills at all: population-average skill profile
    assert row["skill_count_software"] == defaults["skill_count_software"]


def test_train_ensemble_metrics_ablation_and_artifact_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("careermind_ml.career_prediction.ensemble.ARTIFACTS_DIR", tmp_path)
    students = _make_students(20)
    metrics = train_ensemble({"students": students}, FAST_CONFIG)

    assert metrics["n_students"] == 120
    assert metrics["with_preferences"]["accuracy"] > 0.8  # separable one-hot prefs
    assert "without_preferences" in metrics  # ablation always reported
    assert 0.0 <= metrics["without_preferences"]["accuracy"] <= 1.0

    from careermind_ml.career_prediction.ensemble import load_artifact

    artifact = load_artifact()
    assert artifact["version"]
    assert artifact["classes"] == sorted(CATEGORIES)
    assert list(artifact["columns"]) == list(ALL_COLUMNS)

    row = feature_row(students[0], load_skill_categories(), True, artifact["population_defaults"])
    x = pd.DataFrame([row], columns=artifact["columns"])
    proba = artifact["model"].predict_proba(x)[0]
    assert proba.sum() == pytest.approx(1.0)
    assert set(artifact["classes"]) == set(artifact["model"].classes_)

    assert (tmp_path / "ensemble_spec.json").exists()
    import json

    spec = json.loads((tmp_path / "ensemble_spec.json").read_text())
    assert spec["metrics"]["with_preferences"]["accuracy"] == metrics["with_preferences"]["accuracy"]
    assert ARTIFACTS_DIR  # module still exposes the default for the CLI


def test_train_ensemble_skips_ablation_when_preferences_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr("careermind_ml.career_prediction.ensemble.ARTIFACTS_DIR", tmp_path)
    students = _make_students(5)
    config = {**FAST_CONFIG, "include_preferences": False}
    metrics = train_ensemble({"students": students}, config)
    assert "without_preferences" not in metrics


def test_attribution_top_k_features(tmp_path, monkeypatch):
    students = _make_students(10)
    frame, defaults = build_feature_frame(students, include_preferences=True)
    y = np.asarray([s["label"] for s in students])
    model = build_ensemble(FAST_CONFIG)
    model.fit(frame, y)

    row = frame.iloc[[0]]
    prediction = model.predict(row)[0]
    features = top_contributing_features(model, row, prediction, k=5, baseline=defaults)

    assert len(features) == 5
    assert all(f["feature"] in frame.columns for f in features)
    assert all(isinstance(f["importance"], float) for f in features)
    # sorted by |importance|
    magnitudes = [abs(f["importance"]) for f in features]
    assert magnitudes == sorted(magnitudes, reverse=True)
    # the student's dominant preference should push toward their category
    top = features[0]
    assert top["feature"].startswith("pref_") and top["importance"] > 0


def test_attribution_unknown_prediction_returns_empty():
    students = _make_students(10)
    frame, defaults = build_feature_frame(students, include_preferences=True)
    y = np.asarray([s["label"] for s in students])
    model = build_ensemble(FAST_CONFIG)
    model.fit(frame, y)
    features = top_contributing_features(model, frame.iloc[[0]], "nonexistent", k=5, baseline=defaults)
    assert features == []
