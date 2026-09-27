"""Stage 3: FES-augmented Factorisation Machine scoring (paper Sec. V-B).

Base FM formulation (Rendle [5]) chosen for interpretability and training
tractability. Operates over the full student feature vector: academic,
behavioural (current FES + 14-day FES trend), preference, and contextual —
learning pairwise interactions (e.g., FES x algorithmic performance).

Training: binary implicit-feedback labels (engaged / sampled negative) with
MSE loss (ml/configs/fm.yaml). Ranking = predicted score. Held-out AUC is
printed as a sanity check; the full benchmark is Phase 9.
"""
import json
import pathlib
from datetime import datetime

import numpy as np
import torch
from torch import nn

ARTIFACTS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "artifacts"


class FactorizationMachine(nn.Module):
    """Order-2 FM: y(x) = w0 + sum(w_i x_i) + sum_{i<j} <v_i, v_j> x_i x_j."""

    def __init__(self, n_features: int, k: int = 16):
        super().__init__()
        self.w0 = nn.Parameter(torch.zeros(1))
        self.w = nn.Parameter(torch.zeros(n_features))
        self.v = nn.Parameter(torch.randn(n_features, k) * 0.01)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, n_features). Returns (batch,) FM scores."""
        linear = self.w0 + x @ self.w
        interaction = 0.5 * ((x @ self.v) ** 2 - (x**2) @ (self.v**2)).sum(dim=1)
        return linear + interaction


def _split_by_student(interactions, students_agg, holdout=0.2, seed=0):
    """Student-level train/test split (no leakage across the split)."""
    rng = np.random.default_rng(seed)
    students = [a["student"] for a in students_agg]
    rng.shuffle(students)
    n_test = max(1, int(len(students) * holdout))
    test_students = set(students[:n_test])
    train_inter = [i for i in interactions if i["student"] not in test_students]
    test_inter = [i for i in interactions if i["student"] in test_students]
    train_agg = [a for a in students_agg if a["student"] not in test_students]
    test_agg = [a for a in students_agg if a["student"] in test_students]
    return train_inter, test_inter, train_agg, test_agg


def train_fm(data: dict, config: dict | None = None) -> dict:
    """Train the FM on implicit feedback; returns metrics and saves an artifact.

    Args:
        data: output of features.load_fm_training_data (interactions,
            students_agg, item_vocab).
        config: fm.yaml-style dict (embedding_dim, learning_rate, epochs,
            batch_size, negatives_per_positive).
    """
    from .features import build_spec, make_dataset

    config = config or {}
    k = int(config.get("embedding_dim", 16))
    epochs = int(config.get("epochs", 50))
    batch_size = int(config.get("batch_size", 256))
    lr = float(config.get("learning_rate", 0.01))
    negatives = float(config.get("negatives_per_positive", 2.0))
    seed = int(config.get("seed", 0))

    torch.manual_seed(seed)
    np.random.seed(seed)

    train_inter, test_inter, train_agg, _ = _split_by_student(
        data["interactions"], data["students_agg"], holdout=0.2, seed=seed
    )
    spec = build_spec(data["students_agg"], data["item_vocab"])
    rng = np.random.default_rng(seed)

    x_train, y_train = make_dataset(train_inter, train_agg, spec, negatives, rng)
    x_test, y_test = make_dataset(
        test_inter,
        data["students_agg"],  # spec defaults are population-wide on purpose
        spec,
        negatives,
        rng,
    )

    model = FactorizationMachine(spec.dim, k=k)
    optimiser = torch.optim.Adam(model.parameters(), lr=lr)
    x_train_t = torch.as_tensor(x_train)
    y_train_t = torch.as_tensor(y_train)

    n = len(x_train_t)
    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(n)
        total_loss = 0.0
        for start in range(0, n, batch_size):
            idx = perm[start : start + batch_size]
            optimiser.zero_grad()
            predictions = model(x_train_t[idx])
            loss = nn.functional.mse_loss(predictions, y_train_t[idx])
            loss.backward()
            optimiser.step()
            total_loss += float(loss) * len(idx)
        if epoch == 0 or (epoch + 1) % 10 == 0:
            print(f"  epoch {epoch + 1}/{epochs} train_loss={total_loss / n:.4f}")

    # held-out AUC (Phase 9 does the full benchmark suite)
    model.eval()
    with torch.no_grad():
        scores = model(torch.as_tensor(x_test)).numpy()
    metrics = {"train_rows": int(n), "test_rows": int(len(x_test))}
    if len(np.unique(y_test)) > 1:
        from sklearn.metrics import roc_auc_score

        metrics["test_auc"] = float(roc_auc_score(y_test, scores))
    else:
        metrics["test_auc"] = None

    save_artifact(model, spec, config)
    metrics["artifact"] = str(ARTIFACTS_DIR / "fm.pt")
    print(
        f"FM trained: {metrics['train_rows']} train rows, {metrics['test_rows']} test rows, "
        f"held-out AUC={metrics['test_auc']}"
    )
    return metrics


def save_artifact(model: FactorizationMachine, spec, config: dict) -> None:
    """Persist Q-network weights + feature spec (+ item vocab) for serving."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "n_features": spec.dim, "k": model.v.shape[1]}, ARTIFACTS_DIR / "fm.pt")
    with open(ARTIFACTS_DIR / "fm_spec.json", "w") as fh:
        json.dump(
            {
                "item_vocab": spec.item_vocab,
                "population_grades": spec.population_grades,
                "population_fes": spec.population_fes,
                "population_trend": spec.population_trend,
                "config": config or {},
                "saved_at": datetime.utcnow().isoformat(),
            },
            fh,
            indent=2,
        )


def load_artifact(device: str = "cpu"):
    """Load (eval-mode model, FeatureSpec) for serving."""
    from .features import FeatureSpec

    ckpt = torch.load(ARTIFACTS_DIR / "fm.pt", map_location=device)
    with open(ARTIFACTS_DIR / "fm_spec.json") as fh:
        spec_data = json.load(fh)
    model = FactorizationMachine(ckpt["n_features"], k=ckpt["k"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    spec = FeatureSpec(
        item_vocab=spec_data["item_vocab"],
        population_grades=spec_data["population_grades"],
        population_fes=spec_data["population_fes"],
        population_trend=spec_data["population_trend"],
    )
    return model, spec
