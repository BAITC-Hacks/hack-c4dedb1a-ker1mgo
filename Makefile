PY ?= python
DATA ?= project_docs/data
OUT ?= out

.PHONY: run app test eval eda

run:
	$(PY) -m moneygraph.run --data $(DATA) --out $(OUT)

app:
	$(PY) -m streamlit run app/app.py --server.headless true

test:
	$(PY) -m pytest -q

eval:
	$(PY) -m agent.eval

eda:
	$(PY) -m moneygraph.eda --data $(DATA)
