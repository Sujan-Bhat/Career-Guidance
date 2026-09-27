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
        self.config = config or {}
        self.device = torch.device(device)
        self.q_net = QNetwork(
            state_dim=int(self.config.get("state_dim", 17)),
            n_actions=int(self.config.get("n_actions", 8)),
        ).to(self.device)
        self.target_net = QNetwork(
            state_dim=int(self.config.get("state_dim", 17)),
            n_actions=int(self.config.get("n_actions", 8)),
        ).to(self.device)
        self.target_net.load_state_dict(self.q_net.state_dict())
        for p in self.target_net.parameters():
            p.requires_grad_(False)

        self.gamma = float(self.config.get("gamma", 0.99))
        self.target_update_steps = int(self.config.get("target_update_steps", 100))
        self.optimizer = torch.optim.Adam(
            self.q_net.parameters(), lr=float(self.config.get("learning_rate", 0.0005))
        )
        self.train_steps = 0

    def select_action(self, state: np.ndarray, epsilon: float) -> int:
        """Epsilon-greedy action selection."""
        if np.random.random() < epsilon:
            return int(np.random.randint(8))
        return int(self.q_values(state).argmax())

    def q_values(self, state: np.ndarray) -> np.ndarray:
        """Q(s) for all 8 actions (greedy serving / diagnostics)."""
        with torch.no_grad():
            q = self.q_net(torch.as_tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0))
            return q.squeeze(0).cpu().numpy()

    def train_step(self, batch) -> dict:
        """One gradient step on a replay batch: TD target via target_net
        (Mnih et al.), smooth-L1 loss, target sync every
        `target_update_steps` steps."""
        states, actions, rewards, next_states, dones = batch
        states = torch.as_tensor(np.asarray(states), dtype=torch.float32, device=self.device)
        actions = torch.as_tensor(np.asarray(actions), dtype=torch.int64, device=self.device)
        rewards = torch.as_tensor(np.asarray(rewards), dtype=torch.float32, device=self.device)
        next_states = torch.as_tensor(np.asarray(next_states), dtype=torch.float32, device=self.device)
        dones = torch.as_tensor(np.asarray(dones), dtype=torch.float32, device=self.device)

        q = self.q_net(states).gather(1, actions.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            next_q = self.target_net(next_states).max(dim=1).values
            td_target = rewards + self.gamma * next_q * (1.0 - dones)
        loss = torch.nn.functional.smooth_l1_loss(q, td_target)

        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        self.train_steps += 1
        if self.train_steps % self.target_update_steps == 0:
            self.target_net.load_state_dict(self.q_net.state_dict())

        return {
            "loss": float(loss.item()),
            "td_error": float((q - td_target).abs().mean().item()),
        }

    def save(self, path: str) -> None:
        torch.save({"q_net": self.q_net.state_dict(), "target_net": self.target_net.state_dict()}, path)

    def load(self, path: str) -> None:
        ckpt = torch.load(path, map_location=self.device)
        self.q_net.load_state_dict(ckpt["q_net"])
        self.target_net.load_state_dict(ckpt["target_net"])
