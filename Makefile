.PHONY: install-backend install-ml install-frontend install-all dev seed test lint train-fes train-fm train-dqn train-ensemble

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

test:
	pytest ml/tests llm_gateway/tests backend/apps -q

lint:
	python -m compileall -q backend ml llm_gateway data evaluation

train-fes:
	PYTHONPATH=ml python -m careermind_ml.train --module fes --config ml/configs/fes.yaml

train-fm:
	PYTHONPATH=ml python -m careermind_ml.train --module fm --config ml/configs/fm.yaml

train-dqn:
	PYTHONPATH=ml python -m careermind_ml.train --module dqn --config ml/configs/dqn.yaml

train-ensemble:
	PYTHONPATH=ml python -m careermind_ml.train --module ensemble --config ml/configs/ensemble.yaml
