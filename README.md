# CAREERMIND

A behaviour-aware adaptive career guidance platform implementing the architecture
described in the CAREERMIND research paper: a six-component system (two supporting
layers + four core modules) that integrates hybrid course/career recommendation,
reinforcement-learning-based adaptive feedback, and the novel
**Focus Efficiency Score (FES)** into a single coherent platform.

## About the Project

CAREERMIND targets engineering undergraduates with a closed feedback loop:
behavioural interaction data is converted into a **Focus Efficiency Score (FES)** —
a composite of five sub-metrics (task completion, session consistency,
distraction-free engagement, quiz persistence, resource depth) — which then drives
hybrid career recommendations, adapts a DQN-based feedback policy, and feeds the
career path prediction ensemble.

The project has two AI parts, deliberately decoupled:

- **Part A — External LLM API (`llm_gateway/`):** a provider-agnostic LLM client
  (OpenAI / Anthropic / Gemini) powering conversational career guidance,
  plain-language recommendation explanations (NFR07), and quiz generation.
- **Part B — Own model training (`ml/`):** the paper's models trained from scratch:
  the FES weight calibration (Eq. 2), the 3-stage hybrid cascade recommender
  (knowledge graph → FES-weighted CF → Factorisation Machine), the DQN agent
  (17-dim state, 8 actions, Eq. 3 reward), and the career prediction ensemble
  (Random Forest + Gradient Boosting + MLP with a logistic-regression meta-learner).

## Module Map

| Module | Purpose | Paper section |
|---|---|---|
| `frontend/` | Next.js (TypeScript + Tailwind) UI + behavioural event tracking SDK (User Interaction Layer) | Sec. V |
| `backend/` | Django REST Framework APIs; loads trained model artifacts; serves both Part A and Part B | Sec. V, VI |
| `ml/` | **Part B** — own model training: FES engine, cascade recommender, DQN agent, career ensemble | Sec. V-A–V-D |
| `llm_gateway/` | **Part A** — external LLM API integration: chat, explanations, quiz generation | NFR07 |
| `data/` | OULAD downloader + schema mapper, synthetic student simulator (latent parameters, OULAD-calibrated), career knowledge-graph seed, Mongo seeder | Sec. VIII |
| `evaluation/` | Pilot-study benchmarks, metrics (P@k / R@k / nDCG@k), sensitivity analysis | Sec. VII–VIII |
| `infra/` | docker-compose (web, frontend, mongo, redis, celery) | Sec. VI |
| `docs/` | Architecture description (Fig. 1) | Sec. V |

## Tech Stack

- **Backend:** Python 3.10+ · Django 5 · Django REST Framework · SimpleJWT · MongoEngine · Celery · Redis
- **Frontend:** Next.js 14 (App Router) · TypeScript · Tailwind CSS · TanStack Query · axios
- **Database:** MongoDB (flexible multi-dimensional student profiles)
- **ML (Part B):** PyTorch (DQN, FM) · scikit-learn (ensemble) · scipy/pandas (FES) · networkx (knowledge graph) · gymnasium (RL environment)

## Project Structure

```
careermind/
├── frontend/      # Next.js UI + behavioural tracking SDK
├── backend/       # Django REST API (8 apps under apps/)
├── ml/            # Part B: careermind_ml training package + configs + tests
├── llm_gateway/   # Part A: careermind_llm package (provider adapters)
├── data/          # OULAD downloader + schema mapper, student simulator, careers seed, Mongo seeder
├── evaluation/    # metrics, baselines, pilot study runner, sensitivity analysis
├── infra/         # docker-compose.yml
├── docs/          # architecture.md (Fig. 1)
├── Makefile       # common commands
└── .env.example   # environment template
```

## Prerequisites

- **Python 3.10+** (3.11/3.12 recommended) with `pip` and `venv`
- **Node.js 20+** with npm
- **MongoDB 7** — local install or Docker
- **Redis 7** — local install or Docker
- **Docker + Docker Compose** (only for the one-command option)
- An **LLM API key** (OpenAI, Anthropic, or Gemini) for Part A features

## How to Run

### Option A — One command with Docker Compose

```bash
cp .env.example .env        # fill in secrets (LLM API key, Django secret)
make dev                    # mongo + redis + backend(:8000) + celery + frontend(:3000)

# in a second terminal — load data into the (fresh) compose Mongo
docker compose -f infra/docker-compose.yml run --rm web python /app/data/seeds/seed_mongo.py
```

Then open http://localhost:3000 (frontend) and http://localhost:8000/api/v1/ (API).
The images bake in `careermind_ml`/`careermind_llm` (editable) and the trained
artifacts under `ml/artifacts/` — run `make train-fes train-fm train-dqn
train-ensemble` on the host first if they are missing, then rebuild.

### Option B — Run locally, module by module

**1. Start MongoDB and Redis** (skip if already running):

```bash
docker run -d -p 27017:27017 mongo:7
docker run -d -p 6379:6379 redis:7-alpine
```

**2. Configure environment:**

```bash
cp .env.example .env
```

**3. Install and start the backend** (http://localhost:8000):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && python manage.py runserver
```

**4. Load the data foundation into MongoDB** (Phase 1):

```bash
# OULAD: official URLs first, falls back to a verified GitHub mirror
# (all 7 CSVs match the published row counts)
python data/oulad/download.py --out data/oulad/raw/

# Map OULAD tables -> CAREERMIND schema (profiles, sessions, events, resources)
python data/oulad/map_oulad.py --limit-students 200 --with-events

# Seed the career knowledge graph + 200 synthetic students
# (latent-parameter simulator, calibrated to OULAD marginals)
python data/seeds/seed_mongo.py --students 200
# -> 20 skills, 18 career pathways, 200 OULAD + 200 synthetic profiles
```

**5. Install and start the frontend** (http://localhost:3000):

```bash
cd frontend
npm install
npm run dev
```

**6. (Optional) Install the ML packages for development:**

```bash
pip install -e "ml[dev]"        # Part B — pulls torch, sklearn, gymnasium
pip install -e "llm_gateway[dev]"  # Part A — provider SDKs optional
```

### What you should see

- **Frontend:** every page is live — landing, login, dashboard (FES ring +
  14-day trend + sub-metrics), career prediction distribution, recommendations
  (accept/reject + LLM "Why this?" explanations), skill quizzes (seeded demos +
  AI generation), and the guidance chat (friendly degradation without
  `LLM_API_KEY`).
- **Backend:** every endpoint implemented (no 501 stubs remain) — FES,
  recommendations, career prediction, RL feedback, quiz/courses, collector, and
  the LLM proxy; JWT required where noted. LLM endpoints return 503 until
  `LLM_API_KEY` is set (see `.env.example`; the backend loads the repo-root
  `.env` automatically).
- **MongoDB** (after the data-foundation steps): 18 career pathways + 20 skills,
  200 OULAD + 200 synthetic student profiles (+ registered users), ~13.5k
  behavioural sessions, ~101k events, 6.4k learning resources, 4.3k learning
  interactions, 4 demo quizzes (20 items), and the FES history/weight
  collections.
- **Evaluation:** `make eval` runs the four pilot studies and writes
  `evaluation/results/pilot_results.json` (FES validity, recommender
  benchmark, DQN convergence, sensitivity sweeps).

## Testing

```bash
# full suite: ML package + LLM gateway + evaluation + backend (venv-aware,
# per-suite invocations — ml/tests, llm_gateway/tests and evaluation/tests
# all own the `tests` package)
make test

# single suites, e.g.:
cd backend && python -m pytest apps
PYTHONPATH=ml python -m pytest ml/tests
# ML suite includes Phase 1 simulator validation: TCR↔ability, QAP↔motivation
# and outcome↔ability correlations, determinism, KG eligibility math
```

## Pilot study (evaluation)

```bash
make eval      # PYTHONPATH=ml:evaluation python evaluation/run_pilot.py
```

Four studies (paper Sec. VIII), results also written to
`evaluation/results/pilot_results.json`:

1. **FES predictive validity** — Pearson r of FES/sub-metrics vs mean grade
   (TCR strongest ≈ 0.64; per-student Eq. 2 weights vs the 3-student
   population fallback, whose n=3 group correlations are illustrative only).
2. **Recommender benchmark** — leave-one-out over interactions: the 3-stage
   cascade reaches Hit@10 ≈ 0.84 alongside single-technique baselines
   (fm_only ≈ 0.86, cf_only ≈ 0.79, popularity ≈ 0.72, kg_only ≈ 0.55); the
   stage-1 gate passes on average 16.2 of 18 pathways at the paper's 0.6
   threshold.
3. **DQN convergence** — training curve read from
   `ml/artifacts/dqn_training.json` (reward climbs ≈ +6.5 → +8.9 over
   1000 episodes).
4. **Sensitivity** — sweeps over the stage-1 gate (hit@k 0.86 → 0.51 across
   0.4 → 0.8), EngagementSignal thresholds (the interaction-rate threshold is
   the binding constraint: positive rate 67% → 2% as it rises 1.5 → 4.0
   actions/min), the ≥8-session calibration gate, and Eq. 3 reward weights
   (γ-heavy weighting dominates in the reward metric).

## Training CLI (Part B)

```bash
python -m careermind_ml.train --module fes      --config ml/configs/fes.yaml
python -m careermind_ml.train --module fm       --config ml/configs/fm.yaml
python -m careermind_ml.train --module dqn      --config ml/configs/dqn.yaml
python -m careermind_ml.train --module ensemble --config ml/configs/ensemble.yaml
```

Paper constants (EngagementSignal thresholds, ≥8-session calibration rule, 10k
replay buffer, target-network sync every 100 steps, Eq. 3 reward weights) live in
`ml/configs/*.yaml`.

## Roadmap (implementation phases)

0. **Skeleton** — structure, stubs, docker-compose, seed data
1. **Data foundation** — OULAD ingestion (verified mirror), 200-student synthetic simulator calibrated to OULAD, knowledge-graph loader, pathways API
2. **FES engine** — five sub-metrics, Eq. 2 per-student weight calibration (gates + population fallback), batch pipeline, FES read APIs
3. **Backend core** — JWT auth (register/login/me/refresh), behavioural collector (session lifecycle + event ingestion), session-end FES via Celery, quiz attempts (FR04), frontend login + JWT'd tracking
4. **Recommender** — 3-stage cascade live: KG filtering (≥60%), FES-weighted CF re-ranking, trained FM (held-out AUC 0.84) with accept/reject logging; population-profile cold start
5. **Career prediction ensemble** — stacking RF+GBT+MLP → LR meta (held-out acc 0.93 incl. stated preferences; no-preference ablation 0.38), occlusion feature attribution, `GET /careers/predictions` + live `/prediction` page
6. **RL adaptive feedback** — gymnasium simulator environment with the paper's 8 interventions, Eq. 3 reward (α·dFES + β·dSkill + γ·E + δ·CA), DQN pre-training (1000 episodes / 60k steps, reward +6.5 → +8.9), artifact serving, and `GET /rl/status` + `POST /rl/action` transition-logging API
7. **LLM gateway (Part A)** — OpenAI/Anthropic/Gemini adapters, agency-preserving grounded guidance chat (`POST /llm/chat`, per-student history window), LLM quiz generation (`POST /llm/quiz/generate`), cached recommendation explanations (`GET /recommendations/<id>/explain`), live `/chat` page; 503 without `LLM_API_KEY`, 502 on provider failure
8. **Full frontend** — live recommendations page (cascade provenance, accept/reject, "Why this?" explanations), quiz page (seeded demos + AI generation, per-item attempt recording into QAP), dashboard 14-day FES trend chart, live `/chat` and `/prediction` pages
9. **Evaluation / pilot study** — `evaluation/` package: leave-one-out benchmark (cascade vs kg/cf/fm/popularity, P@k/R@k/nDCG@k/Hit@k + gate pass-rate diagnostic), FES predictive-validity study, DQN convergence readout, and five sensitivity sweeps (Sec. VIII #4); `make eval` runs all four studies into `evaluation/results/pilot_results.json`; simulator fixes surfaced along the way (EngagementSignal action-density reachable, full skill profiles so the eligibility gate measures skill coverage rather than assessment coverage, idempotent event seeding)
10. **Deployment polish** — Dockerfiles rebuilt around a repo-root context so
    the images ship `careermind_ml` + `careermind_llm` (editable) with CPU
    torch, baked artifacts, and the seeder; compose validated end-to-end
    (5 services, in-container seeding, register → recommend → RL E2E smoke);
    `.dockerignore`s, env-backed seeder defaults, and this README/architecture
    pass

See `docs/architecture.md` for the component/data-flow diagram (Fig. 1).
