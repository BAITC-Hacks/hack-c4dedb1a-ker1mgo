# Money graph

Team ker1mGo, case «Граф денег». The offline pipeline assigns roles to 2,248 clients,
groups them into clusters, and ranks who an AML analyst should review first and why.
The Streamlit viewer and optional assistant explore those computed results.
All findings are hypotheses to investigate, not statements of guilt.

## Quickstart

Python 3.12 and `make` are required. Run these commands from the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make run
make app
```

Open <http://localhost:8501>. The pipeline and viewer work without API keys.
`make` uses `.venv/bin/python` when available; override with `PY=/path/to/python`.
For development, install `requirements-dev.txt` and run `make check`.

The supplied task and datasets remain in [`project_docs/`](project_docs/README.md).
`make run` reads `project_docs/data/` and refreshes `out/`, including the untracked
`features.parquet` needed by the viewer. Use `make run OUT=/tmp/moneygraph-output`
to validate without replacing local outputs. CLI defaults resolve from the source
checkout; explicitly supplied relative paths resolve from the working directory.

## Commands

| Command | Purpose |
|---|---|
| `make run` | Compute roles, clusters, priorities, model report and data requests offline |
| `make app` | Launch the viewer on port 8501 |
| `make test` | Run offline tests; generated test outputs go to temporary directories |
| `make lint` | Check imports and common Python errors |
| `make format` | Sort imports and format Python files |
| `make check` | Run lint, formatting checks and tests |
| `make eda` | Print exploratory data findings |
| `make eval` | Evaluate the assistant; requires a configured API key |
| `make docker-up` | Build and launch the pipeline and viewer with Docker Compose |
| `make docker-down` | Stop the containers, retaining the output volume |

Docker Compose runs the offline pipeline first and mounts its output read-only in
the viewer. Set `MONEYGRAPH_PORT` to change the published port. `.env` is optional
and excluded from the image. The Docker launch also requires Compose support for
optional `env_file` entries.

## Structure

```text
moneygraph/       Data loading, analytics, export pipeline and shared paths/formatting
agent/            Read-only graph queries, fact cards and optional chat/evaluation
app/              Streamlit entry point, navigation, resources and charts
  views/          Overview, network, top list, node, assistant and method screens
tests/            Offline regression and integration tests
docs/             Architecture, methodology and assistant reference
project_docs/     Original task, dataset description and supplied parquet data
out/              Reviewed submission artifacts and local generated results
```

The pipeline produces results; the viewer and assistant read them. Each pipeline
step exposes `compute(ctx)` and returns columns keyed by `gid`. Thresholds and
weights belong in [`moneygraph/config.yaml`](moneygraph/config.yaml).

## Outputs

| File in `out/` | Contents |
|---|---|
| `nodes_roles.csv` | Roles, evidence, clusters and priorities for every client |
| `clusters.csv` | Cluster membership counts, top clients and hypotheses |
| `top_nodes.csv` | Ranked clients and reasons to review them |
| `features.parquet` | Computed metrics used by the viewer and assistant |
| `resilience.csv` | Network and seed-flow changes after removing selected clients |
| `data_requests.csv` | Additional data needed to resolve observation gaps |
| `truncation_model.json` | Depth-4 model features, validation and coefficients |
| `agent_eval.csv` | Optional assistant evaluation results from `make eval` |

The reviewed CSVs and model report are tracked submission artifacts. Feature tables,
assistant evaluations and prose caches are local generated files. Refresh submission
artifacts deliberately and review their diff. Fixed seeds control randomized steps;
floating-point eigensolvers can still produce tiny differences across runs or platforms.

The Method screen displays model, resilience and evaluation evidence. It also accepts
optional `bench.csv`, `bench.svg` and `bench_metadata.json` exports when available;
this repository currently has no benchmark generator.

## Optional assistant

Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. `OPENAI_MODEL` and
`OPENAI_BASE_URL` are optional. Chat, evaluation and prose generation can call the
configured provider; ordinary pipeline runs and tests stay offline.
See [assistant setup and tools](docs/assistant.md).

## Reference

- [Architecture and data contract](docs/design.md)
- [Methodology, results and limitations](docs/methodology.md)
- [Development workflow](CONTRIBUTING.md)
- [Agent working instructions](AGENTS.md)
