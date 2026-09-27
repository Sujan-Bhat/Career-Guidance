.PHONY: install-backend install-ml install-frontend install-all dev seed test lint train-fes train-fm train-dqn train-ensemble

# prefer the project venv when it exists
PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python)

install-backend:
	pip install -r backend/requirements.txt

install-ml:
	pip install -e "ml[dev]"
	pip install -e "llm_gateway[dev]"

install-frontend:
	cd frontend && npm install

install-all: install-backend install-ml install-frontend

dev:
	docker compose -f infra/docker-compose.yml up --build

seed:
	python data/seeds/seed_mongo.py --uri $${MONGO_URI:-mongodb://localhost:27017} --db $${MONGO_DB_NAME:-careermind}

# one invocation per suite: ml/tests, llm_gateway/tests and evaluation/tests
# each define a `tests` package, so they cannot share a single pytest process
test:
	PYTHONPATH=ml $(PYTHON) -m pytest ml/tests -q
	$(PYTHON) -m pytest llm_gateway/tests -q
	PYTHONPATH=ml:evaluation $(PYTHON) -m pytest evaluation/tests -q
	PYTHONPATH=ml:backend $(PYTHON) -m pytest backend/apps

lint:
	$(PYTHON) -m compileall -q backend ml llm_gateway data evaluation

eval:
	PYTHONPATH=ml:evaluation $(PYTHON) evaluation/run_pilot.py

train-fes:
	PYTHONPATH=ml $(PYTHON) -m careermind_ml.train --module fes --config ml/configs/fes.yaml

train-fm:
	PYTHONPATH=ml $(PYTHON) -m careermind_ml.train --module fm --config ml/configs/fm.yaml

train-dqn:
	PYTHONPATH=ml $(PYTHON) -m careermind_ml.train --module dqn --config ml/configs/dqn.yaml

train-ensemble:
	PYTHONPATH=ml $(PYTHON) -m careermind_ml.train --module ensemble --config ml/configs/ensemble.yaml
