PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
DATA ?= project_docs/data
OUT ?= out

.PHONY: run app test eval eda lint format format-check check docker-up docker-down

run:
	$(PY) -m moneygraph.run --data "$(DATA)" --out "$(OUT)"

app:
	$(PY) -m streamlit run app/app.py --server.headless true

test:
	$(PY) -m pytest -q

eval:
	$(PY) -m agent.eval

eda:
	$(PY) -m moneygraph.eda --data "$(DATA)"

lint:
	$(PY) -m ruff check .

format:
	$(PY) -m ruff check --select I --fix .
	$(PY) -m ruff format .

format-check:
	$(PY) -m ruff format --check .

check: lint format-check test

docker-up:
	docker compose up --build

docker-down:
	docker compose down
