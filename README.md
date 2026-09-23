# Money graph

**Follow money from known seeds, inspect the evidence, and choose the next data request.**

Team ker1mGo, case «Граф денег». Our case desk turns a four-hop crawl from 81 known couriers into
explainable role hypotheses, communities and a review order for 2,248 clients. Every finding is a hypothesis
for an analyst to check, never an accusation.

![Investigate case desk with the money-flow graph and an evidence dossier](docs/media/investigate.png)

What makes this approach useful:

- **Seed-money attribution.** A KZT-weighted, outflow-capped propagation estimates where seed-originated money reaches.
  Priority combines that evidence with roles, source convergence and removal impact; PageRank alone does not decide the queue.
- **Honest treatment of the crawl boundary.** An inbound-only forwarding model learns from depths 1–3 and distinguishes
  observed terminal-role hypotheses from inferred ones at depth 4.
- **A ranking that can be challenged.** Resilience compares priority with degree, degree excluding seeds, and random removal.
  We show where degree wins and where priority cuts more seed-money flow.
- **Action after uncertainty.** Exported data requests identify the next outgoing crawl, missing seed inflows and small components to inspect.
- **A guarded optional assistant.** Graph tools, identifier checks and an evaluation generated from the current graph support natural-language investigation.
  The pipeline and complete viewer work without a model connection.

| Naive interpretation | Our treatment |
|---|---|
| No observed outflow means terminal | 444 depth-4 sinks have **unverified** outflow; their outgoing transfers were never crawled |
| Every terminal label means the same thing | 1,071 observed and 62 inferred terminal-role hypotheses remain visibly distinct |
| Largest degree is the best review order | Compare disruption and seed-money reach before choosing a priority strategy |
| A score is enough | Open the rule trace, nearest missed rule, priority contributions and seed-money path evidence |

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
`make run` reads `project_docs/data/` and refreshes `out/`, including the exported graph evidence
and `features.parquet` used by the viewer. Use `make run OUT=/tmp/moneygraph-output`
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
| `make bench` | Generate offline scale measurements and a standalone chart |
| `make eval` | Evaluate the assistant; requires a configured API key |
| `make docker-up` | Build and launch the pipeline and viewer with Docker Compose |
| `make docker-down` | Stop the containers, retaining the output volume |

Docker Compose runs the offline pipeline first and mounts its output read-only in
the viewer. Set `MONEYGRAPH_PORT` to change the published port. `.env` is optional
and excluded from the image. The Docker launch also requires Compose support for
optional `env_file` entries.

## A five-minute case walkthrough


1. **Case overview:** read the scope and boundary caveats, then open the first review candidate.
2. **Investigate:** search any part of a gid, focus a client, expand one or two hops, and follow transfer arrows.
   Open the dossier's role conditions, priority contributions and estimated seed-money paths.
3. **Clusters and Priorities:** compare group hypotheses and inspect why a client enters the review queue.
4. **Data gaps:** export requests for the next crawl instead of treating missing outflow as a finding.
5. **Method & scale:** inspect truncation validation, resilience, measured runtime and configuration provenance.
   The **Assistant** page is optional; every other page works without a key.

## Structure

```text
moneygraph/       Data loading, analytics, export pipeline and shared paths/formatting
agent/            Read-only graph queries, fact cards and optional chat/evaluation
app/              Streamlit entry point, shared UI, dossiers, charts and SVG graph
  pages/          Briefing, investigation, clusters, priorities, data gaps, chat and method
  static/         Bundled fonts and their license
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
| `edges.parquet`, `transactions.parquet` | Exported transfer evidence for read-only consumers |
| `rule_traces.json`, `seed_paths.json` | Rule conditions, nearest missed rules and estimated flow paths |
| `pipeline_metadata.json` | Configuration, runtime settings and measured step timings |
| `bench.csv`, `bench.svg`, `bench_metadata.json` | Measured scale results, chart and environment |
| `resilience.csv` | Network and seed-flow changes after removing selected clients |
| `data_requests.csv` | Additional data needed to resolve observation gaps |
| `truncation_model.json` | Depth-4 model features, validation and coefficients |
| `agent_eval.csv` | Optional assistant evaluation results from `make eval` |

The reviewed CSVs, parquet evidence and explanation files are tracked as a ready-to-open
case snapshot. `make run` rebuilds case evidence; `make bench` separately refreshes scale
measurements. Assistant evaluations remain local. Review generated artifact diffs before
committing them; timing and environment metadata vary by machine.

The Method screen displays model validation, resilience, measured scaling, provenance
and any available assistant evaluation. See [methodology and measurements](docs/methodology.md).

## Optional assistant

Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. `OPENAI_MODEL` and
`OPENAI_BASE_URL` are optional. Chat and evaluation can call the
configured provider; ordinary pipeline runs and tests stay offline.
See [assistant setup and tools](docs/assistant.md).

## Reference

- [Architecture and data contract](docs/design.md)
- [Methodology, results and limitations](docs/methodology.md)
- [Development workflow](CONTRIBUTING.md)
- [Agent working instructions](AGENTS.md)
