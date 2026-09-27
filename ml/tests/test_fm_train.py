"""FM feature + training tests (Phase 4)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from careermind_ml.recommender.features import (  # noqa: E402
    GRADE_SUBJECTS,
    FeatureSpec,
    build_spec,
    make_dataset,
    vectorize,
)
from careermind_ml.recommender.fm import (  # noqa: E402
    FactorizationMachine,
    load_artifact,
    save_artifact,
    train_fm,
)


def _agg(student, stats_grade=80, fes=0.8, pref="data", trend=0.6):
    preferences = {pref: 1.0}
    return {
        "student": student,
        "grades": {s: stats_grade for s in GRADE_SUBJECTS},
        "fes_current": fes,
        "fes_trend": trend,
        "preferences": preferences,
        "year_of_study": 3,
    }


def _data():
    students = [
        _agg(f"s{i:03d}", stats_grade=90 if i % 2 == 0 else 40, pref="data" if i % 2 == 0 else "hardware")
        for i in range(20)
    ]
    interactions = [
        {"student": f"s{i:03d}", "item_id": "c03" if i % 2 == 0 else "c10", "session": f"s{i:03d}:0", "item_type": "pathway", "date": "2025-03-01"}
        for i in range(20)
    ]
    return {"students_agg": students, "interactions": interactions, "item_vocab": ["c03", "c10"]}


def test_vectorize_shape_and_missing_fallbacks():
    data = _data()
    spec = build_spec(data["students_agg"], data["item_vocab"])
    assert spec.dim == 14 + len(spec.item_vocab)

    vec = vectorize(data["students_agg"][0], "c03", spec)
    assert vec.shape == (spec.dim,)
    assert vec.dtype == np.float32
    assert vec[14 + spec.item_vocab.index("c03")] == 1.0  # one-hot item
    assert vec[-1] == 0.0  # c10 not engaged

    # brand-new user: all defaults, still a valid vector
    cold = vectorize({}, "c10", spec)
    assert np.isfinite(cold).all()
    assert cold[-1] == 1.0  # c10 one-hot (vocab sorted: c03, c10)


def test_make_dataset_labels_and_negatives():
    data = _data()
    spec = build_spec(data["students_agg"], data["item_vocab"])
    x, y = make_dataset(data["interactions"], data["students_agg"], spec, negatives_per_positive=2.0)
    assert len(y) == 60  # 20 positives + 40 negatives
    assert y.sum() == 20
    assert ((y == 0) | (y == 1)).all()


def test_train_fm_learns_separable_signal(tmp_path, monkeypatch):
    """High-grade 'data' students always engage c03; 'hardware' students c10 —
    a few epochs must separate held-out AUC well above chance."""
    from careermind_ml.recommender import fm as fm_module

    monkeypatch.setattr(fm_module, "ARTIFACTS_DIR", tmp_path)
    data = _data()
    metrics = train_fm(
        data,
        {"embedding_dim": 8, "epochs": 30, "batch_size": 64, "learning_rate": 0.05,
         "negatives_per_positive": 2.0, "seed": 0},
    )
    assert metrics["train_rows"] > 0
    assert metrics["test_auc"] is not None and metrics["test_auc"] > 0.7

    model, spec = load_artifact()
    assert isinstance(model, FactorizationMachine)
    assert spec.item_vocab == ["c03", "c10"]
