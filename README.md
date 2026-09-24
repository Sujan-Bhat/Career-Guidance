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
| `data/` | OULAD ingestion, synthetic student simulator, career knowledge-graph seed, Mongo seeding | Sec. VIII |
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
├── data/          # OULAD downloader, simulator, careers_seed.json, Mongo seeder
├── evaluation/    # metrics, baselines, sensitivity analysis, pilot notebook
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
```

Then open http://localhost:3000 (frontend) and http://localhost:8000/api/v1/ (API).

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

**4. Seed the career knowledge graph into MongoDB**

```bash
python data/seeds/seed_mongo.py --uri mongodb://localhost:27017 --db careermind
# -> Seeded: 20 skills, 18 career pathways
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

- **Frontend:** landing page, login, dashboard with the FES score ring,
  recommendations, career prediction distribution, quiz, and guidance chat.
  At Phase 0 these are functional page shells awaiting live data.
- **Backend:** all routes under `/api/v1/…` respond. Stub endpoints return
  `501 {"detail": "Not implemented (Phase X)"}`; authenticated endpoints return
  `401` without a JWT — both are the expected Phase 0 behaviour.

## Testing

```bash
# backend tests (needs backend requirements installed)
cd backend && python -m pytest apps

# ML package tests (torch tests skip if torch is absent)
PYTHONPATH=ml python -m pytest ml/tests

# LLM gateway tests (no provider SDKs needed)
PYTHONPATH=llm_gateway python -m pytest llm_gateway/tests
```

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

0. **Skeleton** (current state) — structure, stubs, docker-compose, seed data
1. Data foundation — OULAD ingestion, synthetic simulator, knowledge graph
2. `ml/fes` — five sub-metrics + Eq. 2 per-student weight calibration
3. Backend core — auth, behavioural collector, session→FES pipeline
4. Recommender — KG filtering, FES-weighted CF, FM scoring, cascade API
5. Career prediction ensemble + feature attribution
6. RL — simulator environment, DQN pre-training, online integration
7. LLM gateway — chat, explanations (NFR07)
8. Full frontend
9. Evaluation / pilot study
10. Deployment polish

See `docs/architecture.md` for the component/data-flow diagram (Fig. 1).
