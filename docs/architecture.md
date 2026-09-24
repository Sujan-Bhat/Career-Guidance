# CAREERMIND System Architecture (Fig. 1)

Six loosely coupled components in a continuous feedback loop, backed by MongoDB.

```
                          ┌───────────────────────────┐
                          │   User Interaction Layer  │
                          │      (Next.js frontend)   │
                          └─────────────┬─────────────┘
                                        │ batched events (10s / 20 events)
                                        ▼
                          ┌───────────────────────────┐
                          │ Behavioural Data Collector │  (supporting layer 2)
                          │ (Django: collector app)    │
                          └──────┬──────────────┬──────┘
                 session-end    │              │ raw events
                                 ▼              ▼
        ┌────────────────────────────┐   ┌────────────────────────────┐
        │  Focus Score Computation   │   │  Hybrid Recommendation Sys │
        │  Engine (FES, Eq. 1-2)     │   │  KG → CF → FM (3-stage)    │
        │  ml/fes  ↔  backend/fes    │   │  ml/recommender            │
        └──────────┬─────────────────┘   └──────────┬─────────────────┘
                   │ FES + 14-day trend              │ ranked items
                   ▼                                 ▼
        ┌────────────────────────────┐   ┌────────────────────────────┐
        │  Reinforcement Learning    │   │  Career Path Prediction    │
        │  Agent (DQN, 17-d state,   │──▶│  Module (RF+GBT+MLP + LR   │
        │  8 actions, Eq. 3 reward)  │   │  meta-learner)            │
        │  ml/rl                     │   │  ml/career_prediction      │
        └──────────┬─────────────────┘   └──────────┬─────────────────┘
                   │ policy adjustments               │ probability dist
                   └───────────────┬────────────────┘
                                   ▼
                     ┌──────────────────────────┐
                     │  llm_gateway (Part A)     │  chat + NFR07 explanations
                     │  via backend/llm_proxy    │
                     └──────────────────────────┘

                     ┌──────────────────────────┐
                     │        MongoDB           │  profiles, sessions, events,
                     │  (mongoengine, Celery/   │  fes_history, fes_weights,
                     │   Redis async jobs)      │  recommendations, rl_log, ...
                     └──────────────────────────┘
```

## Component table

| Component | Code | Paper section | Phase |
|---|---|---|---|
| User Interaction Layer | `frontend/` + `lib/tracking` | V | 8 |
| Behavioural Data Collector | `backend/apps/collector` | V | 3 |
| FES Computation Engine | `ml/careermind_ml/fes` + `backend/apps/fes` | V-A | 2 |
| Hybrid Recommendation System | `ml/careermind_ml/recommender` + `backend/apps/recommendations` | V-B | 4 |
| RL Adaptive Feedback | `ml/careermind_ml/rl` + `backend/apps/rl_feedback` | V-C | 6 |
| Career Path Prediction | `ml/careermind_ml/career_prediction` + `backend/apps/careers` | V-D | 5 |
| LLM Gateway (Part A) | `llm_gateway/` + `backend/apps/llm_proxy` | NFR07 | 7 |

## Data flow (one loop iteration)

1. Student interacts; the tracking SDK batches events to the collector.
2. Session end triggers the FES engine (Celery): five sub-metrics (TCR, SCI,
   DFET, QAP, LRDS) → weighted composite (Eq. 1) with per-student or
   population weights (Eq. 2).
3. The recommender runs the cascade: KG eligibility (≥60% prerequisites) →
   FES-weighted item-to-item CF → FM scoring over the full feature vector
   (including current FES and 14-day trend).
4. The DQN agent observes the 17-dim state, selects one of 8 policy actions,
   and logs the transition; its reward (Eq. 3) weights ΔFES, ΔSkill,
   EngagementSignal, and CareerAlignment.
5. The ensemble predicts a career-category distribution; llm_gateway wraps
   outputs in plain-language explanations (NFR07).
6. Accept/reject decisions feed the next state's acceptance ratio — closing
   the loop.
