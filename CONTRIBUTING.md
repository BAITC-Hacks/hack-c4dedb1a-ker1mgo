# Working on Money graph

## Setup and checks

Use Python 3.12. Create `.venv` as shown in the README, then install the development
requirements (they include runtime dependencies):

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
make check
```

`make check` runs Ruff lint, formatting checks and the offline test suite. Tests run
the pipeline in a temporary directory and never need API credentials. Run
`make format` after code changes, then the focused tests for the affected behavior.
Finish with `make check` once the combined changes are ready.

Inspect the branch and working tree before editing. Fetch the remote and sync the
intended base before starting a cleanup or feature branch. Preserve unrelated local
work; do not overwrite output files or switch branches blindly. Commit and push only
when requested, with focused diffs and short, descriptive messages.

## Where code belongs

| Area | Responsibility | Focused checks |
|---|---|---|
| `moneygraph/` | Loading, analytics, rules, configuration and export | `tests/test_rules.py`, `tests/test_outputs.py`, `tests/test_no_hardcode.py`, `tests/test_explainability.py`, `tests/test_scale.py` |
| `agent/` | Graph queries, fact cards, citations and optional model integration | `tests/test_store.py`, `tests/test_agent.py` |
| `app/` | Screen rendering, navigation, charts and cached resources | `tests/test_app.py`, `tests/test_graphview.py` |
| Root tooling and `docs/` | Dependencies, developer commands and shared contracts | `make check`, command/document link checks as relevant |

Keep source packages at the root so `python -m moneygraph.run`, `python -m agent.eval`
and `streamlit run app/app.py` work directly from a checkout. Shared filesystem
locations live in `moneygraph/paths.py`; presentation amount formatting lives in
`moneygraph/formatting.py`. Avoid dependencies from the analytics package into the UI
or optional assistant libraries.

## Data and behavior contracts

Read [the architecture](docs/design.md) for the pipeline order and output schemas.
Keep required output columns stable; additional columns are allowed. Thresholds and
weights belong in `moneygraph/config.yaml`, with an explanation. Do not hardcode client
gids or bake generated results into runtime rules.

Client identifiers are 18-digit integers internally and strings at JSON/model/UI
boundaries. Access `flags` with `row["flags"]` because pandas also has a `flags`
attribute. Seed inflows are incomplete; seed roles cannot depend on `in_kzt` or
`pass_through`. Depth-4 sinks must retain their uncertainty.

The original task and data under `project_docs/` are inputs. `out/` contains reviewed
submission artifacts plus local runtime results. To compare pipeline changes without
overwriting them:

```bash
make run OUT=/tmp/moneygraph-review
```

Model-backed evaluation is optional and makes provider calls. Run `make eval` only
when that evaluation is requested. Keep `.env`, keys, local handoff notes and caches
out of commits and container images.

## Working in parallel

Use the same boundaries for humans and coding agents. Assign each worker an explicit
file scope, expected behavior and focused validation. One integrator owns shared
configuration, dependency files, paths and documentation. Agree on shared interfaces
before workers import them. Avoid two workers editing one file concurrently.

Review the combined diff and run the full offline checks once workers finish. Do not
launch several copies of the full pipeline test suite when a focused check suffices.
Current architecture lives in `docs/design.md`; historical hackathon plans and starter
code remain available in Git history.
