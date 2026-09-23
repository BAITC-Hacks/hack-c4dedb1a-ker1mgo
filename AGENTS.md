# Repository guide

## Start here

- Work from this directory, the Git repository root. Its parent is only a workspace.
- Check `git status --short --branch` and the intended base before edits. Fetch and
  sync that base before implementing changes; preserve existing local work.
- Read `README.md` for commands and layout, then only the modules and tests needed.
  Read `docs/design.md` when changing contracts and `docs/methodology.md` when changing rules.
- Use `rg` with a relevant directory scope. Exclude `.venv/`, `.git/`, generated
  outputs and datasets from broad source searches. Never print `.env` or credentials.

## Ownership and parallel work

- `moneygraph/`: offline pipeline and analytics; `tests/test_rules.py`,
  `tests/test_outputs.py`, `tests/test_no_hardcode.py`, `tests/conftest.py`,
  `tests/test_explainability.py`, `tests/test_scale.py`.
- `agent/`: queries and optional model integration; `tests/test_store.py`, `tests/test_agent.py`.
- `app/`: Streamlit screens and presentation; `tests/test_app.py`, `tests/test_graphview.py`.
- The integrator owns shared paths/formatting, dependencies, tooling and docs.
- Delegate independent work with disjoint files and clear acceptance checks. Keep
  small edits local. Agree on shared interfaces before edits and report changes,
  checks and unresolved risks. Finish with one integrated validation run.

## Preserve these contracts

- The pipeline is offline and never imports UI or model libraries. The viewer and
  assistant read pipeline exports; they do not recompute roles or priority.
- `compute(ctx)` returns one row per input gid with no overwritten feature columns.
- Keep required CSV columns stable and thresholds in `moneygraph/config.yaml`.
- No hardcoded client gids. Use strings for gids at JSON/model/UI boundaries.
- Use `row["flags"]`, not `.flags`. Seed roles must not use incomplete inflows or
  pass-through; depth-4 sinks must not be labeled observed terminals.
- Shared defaults come from `moneygraph.paths`. Preserve explicitly supplied paths.
- Do not change supplied data, existing local outputs, credentials or unrelated
  user edits. Generate verification outputs in temporary directories.

## Validation and handoff

- Use `make format` and focused offline tests during work; `make check` before handoff.
- `make` selects `.venv/bin/python` when present. Install developer tools with
  `.venv/bin/python -m pip install -r requirements-dev.txt` when needed.
- Preserve optional dependencies: deterministic store/card/viewer imports must work
  without importing LangChain/LangGraph. Never make real provider calls in tests.
- Avoid dependency upgrades and speculative abstractions in structural refactors.
- Report what changed, the checks run and remaining limitations. Do not commit,
  push, deploy or run paid evaluations unless requested.
