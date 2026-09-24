"""DQN agent (paper Sec. V-C; Mnih et al. [8]; Sutton & Barto [7] MDP formalism).

Experience replay (10,000 transitions) + target network updated every 100
steps. Pre-trained on simulated student trajectories before online deployment.
"""
import numpy as np
import torch
from torch import nn


class QNetwork(nn.Module):
    """Q(s): 17-dim state -> 8 action values."""

    def __init__(self, state_dim: int = 17, n_actions: int = 8, hidden: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        return self.net(state)


class DQNAgent:
    def __init__(self, config: dict, device: str = "cpu"):
        self.config = config
        self.device = torch.device(device)
        self.q_net = QNetwork().to(self.device)
        self.target_net = QNetwork().to(self.device)
        self.target_net.load_state_dict(self.q_net.state_dict())
        for p in self.target_net.parameters():
            p.requires_grad_(False)

    def select_action(self, state: np.ndarray, epsilon: float) -> int:
        """Epsilon-greedy action selection."""
        if np.random.random() < epsilon:
            return int(np.random.randint(8))
        with torch.no_grad():
            q = self.q_net(torch.as_tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0))
            return int(q.argmax(dim=1).item())

    def train_step(self, batch) -> dict:
        """One gradient step on a replay batch: TD target via target_net,
        sync target every `target_update_steps` steps (Phase 6)."""
        raise NotImplementedError("Phase 6")

    def save(self, path: str) -> None:
        torch.save({"q_net": self.q_net.state_dict(), "target_net": self.target_net.state_dict()}, path)

    def load(self, path: str) -> None:
        ckpt = torch.load(path, map_location=self.device)
        self.q_net.load_state_dict(ckpt["q_net"])
        self.target_net.load_state_dict(ckpt["target_net"])
