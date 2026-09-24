"""Stage 3: FES-augmented Factorisation Machine scoring (paper Sec. V-B).

Base FM formulation (Rendle [5]) chosen for interpretability and training
tractability. Operates over the full student feature vector: academic,
behavioural (current FES + 14-day FES trend), preference, and contextual —
learning pairwise interactions (e.g., FES x algorithmic performance).
"""
import torch
from torch import nn


class FactorizationMachine(nn.Module):
    """Order-2 Factorisation Machine: y(x) = w0 + sum(w_i x_i) + sum_{i<j} <v_i, v_j> x_i x_j."""

    def __init__(self, n_features: int, k: int = 16):
        super().__init__()
        self.w0 = nn.Parameter(torch.zeros(1))
        self.w = nn.Parameter(torch.zeros(n_features))
        self.v = nn.Parameter(torch.randn(n_features, k) * 0.01)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, n_features). Returns (batch,) FM scores."""
        linear = self.w0 + x @ self.w
        # O(kn) pairwise-interaction formulation
        interaction = 0.5 * ( (x @ self.v) ** 2 - (x ** 2) @ (self.v ** 2) ).sum(dim=1)
        return linear + interaction


def train_fm(train_features, train_targets, config: dict):
    """Phase 4: train the FM on (student, item) features with
    accept/reject + implicit-feedback targets; save artifact to ml/artifacts/."""
    raise NotImplementedError("Phase 4")
