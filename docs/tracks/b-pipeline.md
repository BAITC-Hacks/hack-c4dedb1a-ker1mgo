# Track B: pipeline, ranking, delivery

Owns: `moneygraph/data.py clusters.py priority.py export.py run.py config.yaml`, `tests/` (except rules/store),
`README.md`, `Makefile`, `requirements.txt`, `.env.example`. Also the shared contract in [../design.md](../design.md).

Each milestone ends with a push (see "When to push" in [CONTRIBUTING.md](../../CONTRIBUTING.md)). Tick the box in the same push.

- [x] **B1 · scaffold + stub pipeline**
  Layout, pinned requirements, Makefile, config.yaml, `run.py` merging `compute(ctx)` steps, `export.py` writing all outputs in contract schema.

- [x] **B2 · output tests**
  `test_outputs.py` (schema, 2,248 rows, evidence, clusters, top list, runtime) and `test_no_hardcode.py`.

- [x] **B3 · clusters.py** (target 1:15, checkpoint 1)
  Replace the connected-components stub with Louvain on the undirected projection, `weight = log1p(sum_kzt)`, seed and resolution from config.
  Keep `cluster_id = 0` for nodes with no edges. Hypothesis templates in `summarize()` (see design; add `dominant_roles` and `seed_flow_in` columns once A's roles land).
  *Done when:* about 8 clusters with more than one seed, and the run output is stable across two runs.
  **Push. Checkpoint 1.**

- [x] **B4 · priority.py** (target 2:15, checkpoint 2)
  Percentile-ranked components with weights from config, seed factor, removal impact for the pre-ranked top `removal_candidates` (rerun A's seed flow with the node removed),
  `prio_components` as JSON, `why` naming the top 2–3 contributions with numbers. `resilience()`: top-N by priority vs degree vs random (mean of 5 draws), N ∈ {0, 5, 10, 20, 50}.
  *Done when:* the top 30 by priority is mostly non-seed consolidators, distributors and coordinators, and the priority curve in resilience drops faster than the degree curve (if not, write down why).
  **Push. Checkpoint 2.**
  *Result:* top 30 = 12 transit, 7 coordinators, 6 consolidators, 5 distributors, 0 seeds (after A8). Degree beats priority on both curves, for two reasons:
  8 of the degree top 50 are seeds, so it removes the money's sources (priority discounts seeds on purpose), and the 60-116 recipient hubs
  shatter into singletons when removed. Against `degree_nonseed`, priority cuts seed flow faster (60% left at N=50 vs 85%) but still fragments less.
  Priority targets money flow, not topology.

- [x] **B5 · data_requests.csv** (moved to track C as C8)
  Rows with `gid, reason, suggested_request`: likely-forwarding depth-4 nodes (request hop 5), seeds without outgoing transfers, seeds needing their incoming transfers, small isolated components.
  **Push.**

- [x] **B6 · README** (start at 1:00, final at 3:30)
  One-command quickstart (pipeline, app, optional assistant via `.env`) · mermaid diagram (data → metrics → roles → interface) plus a PNG for the slide ·
  role criteria table with thresholds and reasons · priority formula · cluster method (undirected caveat) · how each of the 8 data limitations from the ТЗ is handled ·
  truncation model results · outputs table · limitations and cautious wording · scaling to ~1M nodes (Polars/DuckDB, igraph/GraphFrames, Leiden, sparse SpMV seed flow, sampled betweenness, WebGL viewer, incremental crawl).
  **Push** each time a section is done.

- [x] **B7 · clean-clone check** (3:50)
  Fresh directory, fresh venv, follow the README literally, time it, and fix anything that needed knowledge not written down.
  **Push**, then tell the team `main` is final.

## Round 2 (from review)

B5 moved to track C (`moneygraph/data_requests.py`, already wired into `run.py`). `run.py` now also writes `out/truncation_model.json`.

> **B4 is unblocked: do it now.** Use `taint.propagate(G, seeds, rounds, removed={gid})` for removal impact (it's built for that).
> Expect the roles from A8/A9 to shift a little; priority must only read columns, never role-specific thresholds.

- [x] **B8 · README fill-in** (by 3:30)
  Priority formula plus weights and the resilience result (priority vs degree vs random) · paste A's Roles/Truncation text · "Limitations of the approach" · "Scaling to ~1M nodes" ·
  outputs table: add `data_requests.csv`, `truncation_model.json`, `agent_eval.csv`. Leave the "Assistant" section to C.
  **Push** each section as it's done.

## Round 4 · reproducibility and evidence

Round 4 ownership: Docker packaging, requirements, Makefile, README, and `app/pages/method.py`.
Analytics owns pipeline exports and benchmark measurements; viewer owns the shared page shell.

- [x] **B9 · one-command Docker launch**
  Python 3.12 slim image, pinned dependencies and a non-root user. Offline pipeline writes a shared output volume;
  the app waits for successful completion, mounts outputs read-only and has an HTTP health check. `.env` is optional.
  *Done when:* a clean `docker compose up --build` runs the pipeline, serves a healthy app without a key,
  and `make run` / `make test` still pass locally. **Push.**
  *Verified:* clean image build; pipeline exited 0 in 15.2 s with networking disabled; app healthy as uid 10001,
  no `.env` in the image, generated outputs available. Local pipeline: 14.1 s; existing suite: 23 passed.

- [x] **B10 · method, scale and jury story**
  README leads with seed-money flow, truncation, resilience, next data requests and guarded assistant evaluation.
  Method page reads only exported outputs and shows measured scaling, pipeline steps, benchmark caveats,
  model cross-validation, configuration provenance and limitations.
  *Done when:* the committed benchmark chart matches `out/bench.csv`, README and the page cite actual measurements,
  page smoke tests pass, and the screenshot is readable at laptop width. **Push.**
  *Verified:* Method page passed smoke checks against the shared viewer shell and current analytics exports,
  including benchmark-mode changes. Browser screenshots reviewed at 1366 px. README and page reference the
  matplotlib chart from measured exact ×1 (4.90 s) and sampled ×1/×10/×100 (2.15/17.25/205.83 s) runs;
  benchmark scope, distributions, hardware and approximation caveats are explicit. Temporal reference comparison:
  5.070 s to 0.036 s with output parity. Container rebuilt with pinned matplotlib; dependency check passed.
