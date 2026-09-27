"""Career path prediction ensemble (paper Sec. V-D; Aksenova et al. [29]).

Stacking ensemble: Random Forest + Gradient Boosting + MLP base learners,
combined through a logistic-regression meta-learner trained via
cross-validation. Outputs a confidence-ranked probability distribution over
career categories (not a single deterministic outcome).

Training always reports BOTH feature regimes (Phase 5 decision):
  * full paper features (incl. stated preferences) — the served model
  * a no-preference ablation — honest signal for the pilot study, because
    the simulator derives seeded preferences from the same latent that
    determines the label
"""
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from .features import ALL_COLUMNS, BASE_COLUMNS

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts"
MODEL_VERSION = "ensemble-v1"


def build_ensemble(config: dict):
    """sklearn StackingClassifier with RF/GBT/MLP bases + LR meta (paper)."""
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, StackingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier

    seed = int(config.get("random_state", 42))
    rf_cfg = config.get("random_forest") or {}
    gbt_cfg = config.get("gradient_boosting") or {}
    mlp_cfg = config.get("mlp") or {}

    base_learners = [
        ("random_forest", RandomForestClassifier(n_estimators=int(rf_cfg.get("n_estimators", 300)), random_state=seed, n_jobs=-1)),
        ("gradient_boosting", GradientBoostingClassifier(n_estimators=int(gbt_cfg.get("n_estimators", 200)), random_state=seed)),
        (
            "mlp",
            MLPClassifier(
                hidden_layer_sizes=tuple(mlp_cfg.get("hidden_layer_sizes", [64, 32])),
                max_iter=int(mlp_cfg.get("max_iter", 500)),
                early_stopping=bool(mlp_cfg.get("early_stopping", True)),
                random_state=seed,
            ),
        ),
    ]
    return StackingClassifier(
        estimators=base_learners,
        final_estimator=LogisticRegression(max_iter=1000, random_state=seed),
        cv=int(config.get("cv_folds", 5)),
        stack_method="predict_proba",
        n_jobs=-1,
    )


def _evaluate(model, x_test, y_test) -> dict:
    from sklearn.metrics import accuracy_score, f1_score, log_loss

    proba = model.predict_proba(x_test)
    return {
        "accuracy": float(accuracy_score(y_test, model.predict(x_test))),
        "macro_f1": float(f1_score(y_test, model.predict(x_test), average="macro")),
        "log_loss": float(log_loss(y_test, proba, labels=list(model.classes_))),
    }


def train_ensemble(data: dict, config: dict) -> dict:
    """Cross-validated training; saves the served artifact to ml/artifacts/.

    `data` = load_ensemble_training_data() output. Prints held-out metrics for
    the full model AND the no-preference ablation, then refits the full model
    on all labelled data before saving (metrics stay from the holdout).
    """
    from sklearn.model_selection import train_test_split

    from .features import build_feature_frame

    include_preferences = bool(config.get("include_preferences", True))
    students = [s for s in data["students"] if s.get("label")]
    if len(students) < 10:
        raise ValueError(f"need >= 10 labelled students, got {len(students)}")

    seed = int(config.get("random_state", 42))

    # same split for both regimes (rows are aligned: identical student order)
    full_x, defaults = build_feature_frame(students, include_preferences=True)
    ablate_x, _ = build_feature_frame(students, include_preferences=False, population_defaults=defaults)
    y = np.asarray([s["label"] for s in students])

    indices = np.arange(len(students))
    train_idx, test_idx = train_test_split(
        indices, test_size=float(config.get("test_size", 0.2)), random_state=seed, stratify=y
    )
    x_train, x_test = full_x.iloc[train_idx], full_x.iloc[test_idx]
    xa_train, xa_test = ablate_x.iloc[train_idx], ablate_x.iloc[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    # 1) served model: full paper features
    model = build_ensemble(config)
    model.fit(x_train, y_train)
    metrics = {"n_students": len(students), "n_test": len(test_idx), "with_preferences": _evaluate(model, x_test, y_test)}

    # 2) ablation: no stated preferences (leakage check for the pilot study)
    if include_preferences:
        ablation = build_ensemble(config)
        ablation.fit(xa_train, y_train)
        metrics["without_preferences"] = _evaluate(ablation, xa_test, y_test)

    # refit on all labelled data for maximum serving quality
    model = build_ensemble(config)
    model.fit(full_x, y)

    save_artifact(model, defaults, list(model.classes_), config, metrics)

    wp = metrics["with_preferences"]
    print(
        f"Ensemble trained: {metrics['n_students']} labelled students "
        f"({metrics['n_test']} held out) | full features -> "
        f"acc={wp['accuracy']:.3f} macro-F1={wp['macro_f1']:.3f} log-loss={wp['log_loss']:.3f}"
    )
    if "without_preferences" in metrics:
        wo = metrics["without_preferences"]
        print(
            f"  no-preference ablation -> acc={wo['accuracy']:.3f} "
            f"macro-F1={wo['macro_f1']:.3f} log-loss={wo['log_loss']:.3f}"
        )
    metrics["artifact"] = str(ARTIFACTS_DIR / "ensemble.joblib")
    return metrics


def save_artifact(model, population_defaults: dict, classes: list[str], config: dict, metrics: dict) -> None:
    """Persist the fitted stack + population defaults + class order."""
    import joblib

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    columns = ALL_COLUMNS if bool(config.get("include_preferences", True)) else BASE_COLUMNS
    joblib.dump(
        {
            "model": model,
            "columns": list(columns),
            "population_defaults": population_defaults,
            "classes": classes,
            "version": MODEL_VERSION,
        },
        ARTIFACTS_DIR / "ensemble.joblib",
    )
    with open(ARTIFACTS_DIR / "ensemble_spec.json", "w") as fh:
        json.dump(
            {
                "version": MODEL_VERSION,
                "columns": list(columns),
                "classes": classes,
                "metrics": {k: v for k, v in metrics.items() if k != "artifact"},
                "config": config or {},
                "saved_at": datetime.utcnow().isoformat(),
            },
            fh,
            indent=2,
        )


def load_artifact() -> dict:
    """Load the served artifact: {model, columns, population_defaults,
    classes, version}. Raises FileNotFoundError until `make train-ensemble`
    has run."""
    import joblib

    path = ARTIFACTS_DIR / "ensemble.joblib"
    if not path.exists():
        raise FileNotFoundError(path)
    return joblib.load(path)
