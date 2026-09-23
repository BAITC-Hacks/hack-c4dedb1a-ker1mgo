# Contributing

## Setup

Use Python 3.12. Create `.venv` as in the README, then install the development tools
(they include the runtime dependencies):

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
make check          # Ruff lint, formatting check and the offline test suite
```

Tests run the pipeline in a temporary directory and never need API keys. Run
`make format` after code changes.

## Where code belongs

| Area | Responsibility | Tests |
|---|---|---|
| `moneygraph/` | Loading, analytics, rules, configuration and export | `test_rules.py`, `test_outputs.py`, `test_no_hardcode.py`, `test_explainability.py`, `test_scale.py` |
| `agent/` | Read-only graph queries, fact cards, citations and the optional assistant | `test_store.py`, `test_agent.py` |
| `app/` | Streamlit pages, dossier, charts and the SVG graph | `test_app.py`, `test_graphview.py` |

The pipeline never imports Streamlit or the assistant libraries, and the viewer and
assistant never assign roles or priorities: they read the exports in `out/`.
Shared paths live in `moneygraph/paths.py` and display formatting in `moneygraph/formatting.py`.

## Rules that keep results explainable

- Thresholds and weights belong in `moneygraph/config.yaml`, each with its reason. No client gids in code.
- Required output columns stay stable; extra columns may be appended (see [docs/design.md](docs/design.md)).
- Client ids are 18-digit integers internally and strings at JSON, model and UI boundaries.
- Read the signal column as `row["flags"]`; pandas also has a `.flags` attribute.
- Seed inflows are incomplete, so seed roles never use `in_kzt` or `pass_through`.
  Depth-4 sinks keep their uncertainty and are never observed terminals.

## Changing results

`project_docs/` holds the supplied task and data and is never modified. `out/` is the
committed case snapshot. To compare a change without overwriting it:

```bash
make run OUT=/tmp/moneygraph-review
```

If outputs change on purpose, rerun `make run`, review the diff and commit the new snapshot
together with the code change. `make bench` refreshes the scale measurements separately.
`make eval` calls the configured model provider, so run it only when needed. Keep `.env`
and keys out of commits.

## Branches

Work on a feature branch, keep commits small, and merge into `main` only after
`make check` passes on the combined code.
