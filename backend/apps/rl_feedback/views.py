"""RL adaptive-feedback API (paper FR07, Sec. V-C): policy status + DQN action.

`POST /rl/action` serves a greedy policy action for the student's 17-dim
state and closes out the previous pending transition with an online
Eq. 3 reward (alpha-dFES + gamma-E terms; beta/delta need offline skill and
affinity snapshots unavailable at serving time).
"""
from datetime import datetime
from functools import lru_cache

import numpy as np
from mongoengine import connection
from rest_framework.response import Response
from rest_framework.views import APIView

from careermind_ml.rl.environment import ACTION_NAMES

from .models import RLTransition

_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        from careermind_ml.rl.train import load_agent

        _agent = load_agent()
    return _agent


@lru_cache(maxsize=1)
def _reward_weights() -> dict:
    """Eq. 3 weights from ml/configs/dqn.yaml (single source of truth)."""
    import pathlib

    import yaml

    import careermind_ml

    cfg = pathlib.Path(careermind_ml.__file__).resolve().parents[1] / "configs" / "dqn.yaml"
    with open(cfg) as fh:
        return dict((yaml.safe_load(fh) or {}).get("reward_weights") or {})


def _latest_engagement(student: str) -> int:
    from careermind_ml.fes.engagement import engagement_signal

    db = connection.get_db("default")
    session = db.sessions.find_one({"student": student}, sort=[("date", -1), ("session_index", -1)])
    if not session:
        return 0
    duration = float(session.get("duration_minutes") or 0.0)
    interactions = int(session.get("interaction_count") or 0)
    return engagement_signal(
        duration,
        interaction_count=interactions,
        quiz_attempt_rate=min(1.0, (session.get("quiz_items") or 0) / 5.0),
        interaction_rate=(interactions / duration) if duration > 0 else None,
    )


def _student_state(profile) -> list[float]:
    """17-dim serving state, same layout as the pre-training environment."""
    from apps.careers.models import CareerPathway
    from apps.fes.models import FESScore
    from apps.recommendations.models import Recommendation
    from careermind_ml.recommender.features import GRADE_SUBJECTS

    fes_values = [s.fes for s in FESScore.objects(student=profile.student_id).order_by("computed_at")][-5:]
    fes_part = list(fes_values) + [0.0] * (5 - len(fes_values))

    grades = {r.subject: r.grade for r in profile.academic_records}
    grade_part = [(grades.get(subject) or 70.0) / 100.0 for subject in GRADE_SUBJECTS]

    scores = sorted((a.score for a in profile.skill_assessments), reverse=True)[:5]
    skill_part = [s / 100.0 for s in scores] + [0.0] * (5 - len(scores))

    # active pathway: latest accepted (else latest any) recommendation
    pathway_ids = sorted(p.external_id for p in CareerPathway.objects.only("external_id"))
    recent = list(Recommendation.objects(student=profile.student_id).order_by("-created_at")[:10])
    active = next((r for r in recent if r.decision == "accepted"), recent[0] if recent else None)
    index = pathway_ids.index(active.item_id) if active and active.item_id in pathway_ids else 0

    accepted = sum(1 for r in recent if r.decision == "accepted")
    acceptance = (accepted / len(recent)) if recent else 0.5

    state = fes_part + grade_part + skill_part + [index / 17.0, acceptance]
    if len(state) != 17:
        raise ValueError(f"state must be 17-dim, got {len(state)}")
    return [float(v) for v in state]


class RLStatusView(APIView):
    """Current policy status for the student (active pathway, last action)."""

    def get(self, request):
        from careermind_ml.rl.train import ARTIFACTS_DIR

        transitions = RLTransition.objects(student=request.user.student_id).order_by("-created_at")
        last = transitions.first()
        return Response(
            {
                "model_available": _agent is not None or (ARTIFACTS_DIR / "dqn.pt").exists(),
                "action_names": ACTION_NAMES,
                "transition_count": transitions.count(),
                "last_action": ACTION_NAMES[last.action] if last else None,
                "last_reward": last.reward if last else None,
                "pending_transition": bool(last is not None and not last.done),
            }
        )


class RLActionView(APIView):
    """Select a recommendation-policy adjustment (one of 8 actions) with the
    pre-trained DQN over the 17-dim state; logs the RLTransition."""

    def post(self, request):
        try:
            agent = _get_agent()
        except FileNotFoundError:
            return Response(
                {"detail": "DQN artifact missing — run `make train-dqn` first"}, status=503
            )

        state = _student_state(request.user)

        # close out the previous pending transition with an online Eq. 3 reward
        prev = (
            RLTransition.objects(student=request.user.student_id, done=False)
            .order_by("-created_at")
            .first()
        )
        if prev is not None:
            prev_fes = [v for v in prev.state[:5] if v > 0]
            curr_fes = [v for v in state[:5] if v > 0]
            d_fes = (float(np.mean(curr_fes)) - float(np.mean(prev_fes))) if curr_fes and prev_fes else 0.0
            weights = _reward_weights()
            reward = weights.get("alpha", 0.4) * d_fes + weights.get("gamma", 0.1) * _latest_engagement(
                request.user.student_id
            )
            prev.reward = float(reward)
            prev.done = True
            prev.save()

        q_values = agent.q_values(np.asarray(state, dtype=np.float32))
        action = int(q_values.argmax())
        RLTransition(
            student=request.user.student_id,
            state=state,
            action=action,
            reward=0.0,
            done=False,
            created_at=datetime.utcnow(),
        ).save()

        return Response(
            {
                "action": action,
                "action_name": ACTION_NAMES[action],
                "q_values": [float(v) for v in q_values],
                "state": state,
            }
        )
